from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
import sqlite3
import os
from datetime import datetime
from functools import wraps
import cv2
import pytesseract
import re
import pyttsx3
import threading
import csv
from io import StringIO
from werkzeug.security import generate_password_hash, check_password_hash

# ==================== CONFIG ====================


app = Flask(__name__)
app.secret_key = "supersecretkey"  

# Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# OCR keywords
DEPARTMENT_KEYWORDS = [
    "MCA", "MBA", "BCA", "BBA", "BTECH", "MTECH",
    "M.Com", "B.Sc", "M.Sc", "CSE"
]
IGNORE_KEYWORDS = ["college", "institute", "principal", "validity", "year", "batch"]

# Store latest OCR result globally for /ocr_results
latest_ocr_data = {"name": "Not found", "reg_no": "Not found", "department": "Not found"}

# Auto-stop / auto-restart control
capture_active = True
pause_duration = 3  # seconds
lock = threading.Lock()
last_saved_reg_no = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "library_visitors.db")

# ==================== DATABASE INIT ====================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create visitors table if not exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS visitors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        name TEXT,
        department TEXT,
        visit_time TEXT
    )
    """)

    # Create users table if not exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    # Add default admin if no users exist
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        default_password = generate_password_hash("admin123")
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", ("kle_library", default_password))
        print(" Default admin user created (username: kle_library, password: admin123)")

    conn.commit()
    conn.close()

init_db()

# ==================== AUTH DECORATOR ====================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== USER HELPERS ====================

def get_user(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_password(username, new_password):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    hashed_pw = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password = ? WHERE username = ?", (hashed_pw, username))
    conn.commit()
    conn.close()

# ==================== OCR FUNCTIONS ====================

def extract_id_number(lines):
    POSSIBLE_LABELS = [
        "reg no", "registration no", "reg. no", "regno",
        "regn no", "regn.", "reg"
    ]
    for line in lines:
        if any(label in line.lower() for label in POSSIBLE_LABELS):
            match = re.search(
                r"reg(?:istration)?\.?\s*no[:\s]*([A-Z0-9]{6,})",
                line,
                re.IGNORECASE
            )
            if match:
                return match.group(1)
    return "Not found"

def save_to_database(data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    visit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """INSERT INTO visitors (student_id, name, department, visit_time)
           VALUES (?, ?, ?, ?)""",
        (data['reg_no'], data['name'], data['department'], visit_time)
    )
    conn.commit()
    conn.close()

def speak_message(msg):
    engine = pyttsx3.init()
    engine.say(msg)
    engine.runAndWait()

def process_frame_for_ocr(frame):
    global latest_ocr_data, capture_active, last_saved_reg_no
    if not capture_active:
        return

    h, w, _ = frame.shape
    top = int(h * 0.55)
    bottom = int(h * 0.95)
    left = int(w * 0.15)
    right = int(w * 0.85)

    cropped = frame[top:bottom, left:right]
    gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, None, fx=1.8, fy=1.8, interpolation=cv2.INTER_CUBIC)

    ocr_text = pytesseract.image_to_string(resized, config="--oem 3 --psm 6")
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]

    reg_no = extract_id_number(lines)

    department = "Not found"
    name = "Not found"

    for line in lines:
        for dept in DEPARTMENT_KEYWORDS:
            if dept.lower() in line.lower():
                department = dept.upper()
                break
        if department != "Not found":
            break

    for line in lines:
        if any(word in line.lower() for word in IGNORE_KEYWORDS):
            continue
        if "course mca" in line.lower():
            continue
        words = line.split()
        if 1 < len(words) <= 4 and all(w.isalpha() or '.' in w for w in words):
            name = line.strip().title()
            break

    latest_ocr_data = {
        "name": name,
        "reg_no": reg_no,
        "department": department
    }

    if name != "Not found" and reg_no != "Not found" and department != "Not found":
        with lock:
            if last_saved_reg_no != reg_no:
                last_saved_reg_no = reg_no
                speak_message("Details captured successfully")
                capture_active = False

# ==================== VIDEO STREAM GENERATOR ====================

def gen_frames():
    cap = cv2.VideoCapture(0)
    while True:
        success, frame = cap.read()
        if not success:
            break
        process_frame_for_ocr(frame)

        h, w, _ = frame.shape
        top = int(h * 0.55)
        bottom = int(h * 0.95)
        left = int(w * 0.15)
        right = int(w * 0.85)
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
        )

# ==================== ROUTES ====================

@app.route('/')
def home():
    return render_template('live_scan.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/ocr_results')
def ocr_results():
    return jsonify(latest_ocr_data)

@app.route('/login', methods=['GET', 'POST'])
def login():
    session.pop('_flashes', None)
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = get_user(username)
        if user and check_password_hash(user[2], password):
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password", "danger")
    return render_template('login.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        old_pw = request.form.get("old_password")
        new_pw = request.form.get("new_password")
        confirm_pw = request.form.get("confirm_password")
        username = session.get('username', 'admin')  # default admin if not logged in

        user = get_user(username)
        if not user or not check_password_hash(user[2], old_pw):
            flash("Old password is incorrect.", "danger")
            return redirect(url_for('forgot_password'))

        if new_pw != confirm_pw:
            flash("New passwords do not match.", "danger")
            return redirect(url_for('forgot_password'))

        if not new_pw.strip():
            flash("New password cannot be empty.", "danger")
            return redirect(url_for('forgot_password'))

        update_password(username, new_pw.strip())
        flash("Password updated successfully! Please log in with your new password.", "success")
        return redirect(url_for('login'))

    return render_template('forgot_password.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# ==================== SEARCH VISITORS ====================

@app.route("/search_visitors")
def search_visitors():
    student_id = request.args.get("student_id", "").strip()
    department = request.args.get("department", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    query = "SELECT id, student_id, name, department, visit_time FROM visitors WHERE 1=1"
    params = []

    if student_id:
        query += " AND student_id LIKE ?"
        params.append(f"%{student_id}%")
    if department:
        query += " AND department LIKE ?"
        params.append(f"%{department}%")
    if start_date:
        query += " AND DATE(visit_time) >= DATE(?)"
        params.append(start_date)
    if end_date:
        query += " AND DATE(visit_time) <= DATE(?)"
        params.append(end_date)
        
    query += " ORDER BY id DESC"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return jsonify(rows)

@app.route('/get_visitors')
def get_visitors():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """SELECT id, student_id, name, department, visit_time
           FROM visitors ORDER BY visit_time DESC"""
    )
    rows = cursor.fetchall()
    conn.close()
    return jsonify(rows)

@app.route('/get_live_visitors')
def get_live_visitors():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """SELECT id, student_id, name, department, visit_time
           FROM visitors WHERE DATE(visit_time) = DATE(?)
           ORDER BY visit_time DESC""",
        (today,)
    )
    rows = cursor.fetchall()
    conn.close()
    return jsonify(rows)

@app.route('/resume_capture', methods=['POST'])
def resume_capture_route():
    global capture_active, latest_ocr_data
    with lock:
        capture_active = True
        latest_ocr_data = {"name": "Not found", "reg_no": "Not found", "department": "Not found"}
    return jsonify({"status": "ok"})

@app.route('/save_visitor', methods=['POST'])
def save_visitor():
    global capture_active, last_saved_reg_no
    data = request.get_json()
    save_to_database(data)
    last_saved_reg_no = data["reg_no"]
    speak_message("Entry saved successfully")
    capture_active = True
    return jsonify({"status": "ok"})

@app.route('/delete_visitors', methods=['POST'])
@login_required
def delete_visitors():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM visitors")
    conn.commit()
    conn.close()
    flash("All visitor records deleted.", "success")
    return jsonify({"status": "ok"})

@app.route('/delete_all', methods=['POST'])
@login_required
def delete_all():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM visitors")
    conn.commit()
    conn.close()
    flash("All visitor records deleted.", "success")
    return redirect(url_for('dashboard'))

@app.route('/export_csv')
@login_required
def export_csv():
    student_id = request.args.get("student_id", "")
    department = request.args.get("department", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    query = "SELECT id, student_id, name, department, visit_time FROM visitors WHERE 1=1"
    params = []

    if student_id:
        query += " AND student_id LIKE ?"
        params.append(f"%{student_id}%")
    if department:
        query += " AND department LIKE ?"
        params.append(f"%{department}%")
    if start_date:
        query += " AND DATE(visit_time) >= DATE(?)"
        params.append(start_date)
    if end_date:
        query += " AND DATE(visit_time) <= DATE(?)"
        params.append(end_date)

    query += " ORDER BY visit_time DESC"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["ID", "Student ID", "Name", "Department", "Visit Time"])
    cw.writerows(rows)
    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=visitors.csv"}
    )

# ==================== MAIN ====================

if __name__ == '__main__':
    app.run(debug=True)
