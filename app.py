import os
import secrets
from datetime import datetime
from functools import wraps

import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-development-secret")

def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "eventease"),
        port=int(os.getenv("DB_PORT", "4000")),
        ssl_ca=os.getenv(
            "DB_SSL_CA",
            os.path.join(os.path.dirname(__file__), "tidb-ca.pem")
        ),
        ssl_verify_cert=True
    )

@app.before_request
def csrf_protect():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(24)
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        if not secrets.compare_digest(sent, session["csrf_token"]):
            abort(400, description="Invalid form token. Please refresh and try again.")


@app.context_processor
def inject_globals():
    return {"csrf_token": session.get("csrf_token", "")}


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin access is required.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


@app.route("/")
def index():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT e.*, 
        GREATEST(e.capacity - COALESCE(SUM(CASE WHEN b.status='CONFIRMED' THEN b.quantity ELSE 0 END), 0), 0) AS seats_left
        FROM events e LEFT JOIN bookings b ON e.id=b.event_id
        WHERE e.event_date >= NOW() AND e.is_active=1
        GROUP BY e.id ORDER BY e.event_date ASC
    """)
    events = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("index.html", events=events)


@app.route("/event/<int:event_id>")
def event_detail(event_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT e.*,
        GREATEST(e.capacity - COALESCE(SUM(CASE WHEN b.status='CONFIRMED' THEN b.quantity ELSE 0 END), 0), 0) AS seats_left
        FROM events e LEFT JOIN bookings b ON e.id=b.event_id
        WHERE e.id=%s AND e.is_active=1 GROUP BY e.id
    """, (event_id,))
    event = cur.fetchone()
    cur.close()
    conn.close()
    if not event:
        abort(404)
    return render_template("event_detail.html", event=event)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter your name and email. Password must contain at least 8 characters.", "danger")
            return render_template("register.html")
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (name,email,password_hash) VALUES (%s,%s,%s)",
                        (name, email, generate_password_hash(password)))
            conn.commit()
            flash("Account created. You can now log in.", "success")
            return redirect(url_for("login"))
        except mysql.connector.IntegrityError:
            flash("That email is already registered.", "danger")
        finally:
            cur.close()
            conn.close()
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["is_admin"] = bool(user["is_admin"])
            session["csrf_token"] = secrets.token_hex(24)
            flash("Welcome back!", "success")
            return redirect(url_for("admin_dashboard" if user["is_admin"] else "index"))
        flash("Incorrect email or password.", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/book/<int:event_id>", methods=["POST"])
@login_required
def book_event(event_id):
    try:
        quantity = int(request.form.get("quantity", "1"))
        if quantity < 1 or quantity > 10:
            raise ValueError
    except ValueError:
        flash("Choose between 1 and 10 tickets.", "danger")
        return redirect(url_for("event_detail", event_id=event_id))

    conn = get_db()
    try:
        conn.start_transaction()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM events WHERE id=%s AND is_active=1 FOR UPDATE", (event_id,))
        event = cur.fetchone()
        if not event or event["event_date"] <= datetime.now():
            conn.rollback()
            flash("This event is not available for booking.", "danger")
            return redirect(url_for("index"))

        cur.execute("SELECT COALESCE(SUM(quantity),0) AS booked FROM bookings WHERE event_id=%s AND status='CONFIRMED'", (event_id,))
        booked = cur.fetchone()["booked"]
        if booked + quantity > event["capacity"]:
            conn.rollback()
            flash("Not enough tickets are available.", "danger")
            return redirect(url_for("event_detail", event_id=event_id))

        cur.execute("""
            INSERT INTO bookings (user_id,event_id,quantity,total_amount,booking_code)
            VALUES (%s,%s,%s,%s,%s)
        """, (session["user_id"], event_id, quantity, event["price"] * quantity,
              "EVT-" + secrets.token_hex(4).upper()))
        conn.commit()
        flash("Your tickets are booked! View your booking in My Bookings.", "success")
        return redirect(url_for("my_bookings"))
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


@app.route("/my-bookings")
@login_required
def my_bookings():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT b.*, e.title, e.venue, e.event_date
        FROM bookings b JOIN events e ON b.event_id=e.id
        WHERE b.user_id=%s ORDER BY b.booked_at DESC
    """, (session["user_id"],))
    bookings = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("my_bookings.html", bookings=bookings, now=datetime.now())


@app.route("/cancel-booking/<int:booking_id>", methods=["POST"])
@login_required
def cancel_booking(booking_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE bookings SET status='CANCELLED'
        WHERE id=%s AND user_id=%s AND status='CONFIRMED'
    """, (booking_id, session["user_id"]))
    conn.commit()
    changed = cur.rowcount
    cur.close()
    conn.close()
    flash("Booking cancelled." if changed else "Booking could not be cancelled.", "success" if changed else "warning")
    return redirect(url_for("my_bookings"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM events ORDER BY event_date DESC")
    events = cur.fetchall()
    cur.execute("""
        SELECT b.*, u.name AS customer, e.title AS event_title
        FROM bookings b JOIN users u ON b.user_id=u.id
        JOIN events e ON b.event_id=e.id ORDER BY b.booked_at DESC LIMIT 30
    """)
    bookings = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin.html", events=events, bookings=bookings)


@app.route("/admin/events/add", methods=["POST"])
@admin_required
def add_event():
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "Other").strip()
    description = request.form.get("description", "").strip()
    venue = request.form.get("venue", "").strip()
    event_date = request.form.get("event_date", "").strip()
    image_url = request.form.get("image_url", "").strip()
    try:
        price = float(request.form.get("price", "0"))
        capacity = int(request.form.get("capacity", "0"))
        parsed_date = datetime.fromisoformat(event_date)
        if not title or not venue or price < 0 or capacity < 1 or parsed_date <= datetime.now():
            raise ValueError
    except ValueError:
        flash("Check the event details, price, capacity and future date.", "danger")
        return redirect(url_for("admin_dashboard"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO events (title,category,description,venue,event_date,price,capacity,image_url)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (title, category, description, venue, parsed_date, price, capacity, image_url or None))
    conn.commit()
    cur.close()
    conn.close()
    flash("Event added successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/events/<int:event_id>/toggle", methods=["POST"])
@admin_required
def toggle_event(event_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE events SET is_active=1-is_active WHERE id=%s", (event_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Event visibility updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True)
