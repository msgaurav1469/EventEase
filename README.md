# EventEase — Event Management & Ticket Booking

A beginner-friendly full-stack website built with HTML, CSS, Python Flask and MySQL.

## Features
- Browse upcoming events and view event details.
- User registration and login with hashed passwords.
- Book 1–10 tickets while checking available capacity.
- Unique booking code and booking history.
- Cancel confirmed bookings.
- Admin dashboard to add events and hide/publish events.
- MySQL relational database and responsive CSS layout.

> This is an educational project. It records bookings but does not accept online payments.

## Requirements
- Python 3.10 or newer
- MySQL Server 8.x
- VS Code (recommended)

## Setup on Windows (PowerShell)

1. Extract the ZIP and open the `EventEase_Event_Management` folder in VS Code.
2. Open Terminal → New Terminal.
3. Create and activate a virtual environment:

   ```powershell
   py -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, run this for the current terminal only:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\venv\Scripts\Activate.ps1
   ```

4. Install packages:

   ```powershell
   pip install -r requirements.txt
   ```

5. In MySQL Workbench, open `schema.sql` and execute it. It creates the `eventease` database and its three tables.

6. Copy `.env.example` and rename the copy to `.env`. Edit the MySQL username and password:

   ```env
   SECRET_KEY=put-a-long-random-value-here
   DB_HOST=localhost
   DB_USER=root
   DB_PASSWORD=your_mysql_password
   DB_NAME=eventease
   DB_PORT=3306
   ```

   If your MySQL root account has no password, leave `DB_PASSWORD=` blank.

7. Create an administrator account:

   ```powershell
   python create_admin.py
   ```

   Enter an admin name, email and password when prompted.

8. Start the website:

   ```powershell
   python app.py
   ```

9. Open `http://127.0.0.1:5000` in your browser.

## First test
1. Log in with the admin account.
2. Open Admin and add an event with a future date/time.
3. Log out and create a normal user account.
4. Open the event and book tickets.
5. Visit My Bookings to view the booking code or cancel.

## Folder structure

```text
EventEase_Event_Management/
├── app.py
├── create_admin.py
├── schema.sql
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── event_detail.html
│   ├── login.html
│   ├── register.html
│   ├── my_bookings.html
│   ├── admin.html
│   └── 404.html
└── static/
    └── style.css
```

## Important notes
- Never upload your real `.env` file or passwords to GitHub.
- Keep the `venv` folder out of Git; `.gitignore` already excludes it.
- For a public deployment, use a production WSGI server, HTTPS, secure environment variables and a managed MySQL database. Do not use Flask debug mode in production.
