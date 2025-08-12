from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
from datetime import datetime
from functools import wraps
import cv2
import pytesseract
import re
import pyttsx3

# ==================== CONFIG ====================
app = Flask(__name__)
app.secret_key = "supersecretkey"  # Change in production

USERNAME = "admin"
PASSWORD = "1234"

# Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# OCR keywords
DEPARTMENT_KEYWORDS = [
    "MCA", "MBA", "BCA", "BBA", "BTECH", "MTECH", "M.Com", "B.Sc", "M.Sc",
    "CSE", "ECE", "student", "engineer", "developer", "librarian", "faculty"
]
IGNORE_KEYWORDS = ["college", "institute", "principal", "validity", "year", "batch"]

# ==================== AUTH DECORATOR ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== OCR FUNCTION ====================
def extract_id_number(lines):
    POSSIBLE_LABELS = ["reg no", "registration no", "reg. no", "regno", "regn no", "regn.", "reg"]
    for line in lines:
        if any(label in line.lower() for label in POSSIBLE_LABELS):
            match = re.search(r"reg(?:istration)?\.?\s*no[:\s]*([A-Z0-9]{6,})", line, re.IGNORECASE)
            if match:
                return match.group(1)
    return "Not found"

def run_ocr_and_save():
    cap = cv2.VideoCapture(0)
    print("📡 Scanning for ID card... Show the card to the camera.")

    extracted = False
    name, reg_no, department, ocr_text = "Not found", "Not found", "Not found", ""

    while not extracted:
        ret, frame = cap.read()
        if not ret:
            print("❌ Camera error.")
            break

        h, w, _ = frame.shape
        top = int(h * 0.55)
        bottom = int(h * 0.95)
        left = int(w * 0.15)
        right = int(w * 0.85)

        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
        cv2.putText(frame, "Scanning for ID card fields...", (left, top - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        cv2.imshow("ID Card Scanner", frame)
        cv2.moveWindow("ID Card Scanner", 10, 20)

        cropped = frame[top:bottom, left:right]
        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, None, fx=1.8, fy=1.8, interpolation=cv2.INTER_CUBIC)

        ocr_text = pytesseract.image_to_string(resized, config="--oem 3 --psm 6")
        lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]

        reg_no = extract_id_number(lines)

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
            words = line.split()
            if 1 < len(words) <= 4 and all(w.isalpha() or '.' in w for w in words):
                name = line.strip().title()
                break

        if len(reg_no) == 14 and department.strip().lower() == "mca" and name != "Not found":
            engine = pyttsx3.init()
            engine.say("Details captured successfully.")
            engine.runAndWait()

            conn = sqlite3.connect('library_visitors.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO visitors (student_id, name, visit_time, face_match_status, department)
                VALUES (?, ?, ?, ?, ?)
            ''', (reg_no, name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'pending', department))
            conn.commit()
            conn.close()
            print("✅ Data saved to database.")
            extracted = True
            break

        if cv2.waitKey(1) & 0xFF == 27:
            print("❌ ESC pressed. Exiting.")
            break

    cap.release()
    cv2.destroyAllWindows()
    return name, reg_no, department, ocr_text

# ==================== ROUTES ====================
@app.route('/')
def home():
    # Run OCR and show results page (not dashboard directly)
    name, reg_no, department, ocr_text = run_ocr_and_save()
    return render_template('scan_result.html',
                           name=name,
                           reg_no=reg_no,
                           department=department)

@app.route('/scan')
def scan():
    name, reg_no, department, ocr_text = run_ocr_and_save()
    flash("New visitor scanned successfully!", "success")
    return render_template('scan_result.html',
                           name=name,
                           reg_no=reg_no,
                           department=department)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pw = request.form['password']
        if user == USERNAME and pw == PASSWORD:
            session['logged_in'] = True
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/get_visitors')
def get_visitors():
    conn = sqlite3.connect("library_visitors.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, student_id, name, department, visit_time
        FROM visitors
        ORDER BY visit_time DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return jsonify(rows)

@app.route('/get_live_visitors')
def get_live_visitors():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("library_visitors.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, student_id, name, department, visit_time
        FROM visitors
        WHERE DATE(visit_time) = DATE(?)
        ORDER BY visit_time DESC
    """, (today,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify(rows)


# ==================== MAIN ====================
if __name__ == '__main__':
    app.run(debug=True)
