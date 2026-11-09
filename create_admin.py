import os
import getpass
import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    database=os.getenv("DB_NAME", "eventease"),
    port=int(os.getenv("DB_PORT", "3306"))
)
name = input("Admin name: ").strip()
email = input("Admin email: ").strip().lower()
password = getpass.getpass("Admin password (8+ characters): ")
if len(password) < 8:
    raise SystemExit("Password must be at least 8 characters.")
cur = conn.cursor()
cur.execute(
    "INSERT INTO users (name,email,password_hash,is_admin) VALUES (%s,%s,%s,TRUE)",
    (name, email, generate_password_hash(password))
)
conn.commit()
cur.close()
conn.close()
print("Admin account created. Sign in through the website.")
