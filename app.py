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

# Store latest OCR result globally for /ocr_results
latest_ocr_data = {"name": "Not found", "reg_no": "Not found", "department": "Not found"}

# Auto-stop / auto-restart control
capture_active = True
pause_duration = 3  # seconds
lock = threading.Lock()
last_saved_reg_no = None
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # >>> NEW <<<
DB_PATH = os.path.join(BASE_DIR, "library_visitors.db")  # >>> NEW <<<


# ==================== AUTH DECORATOR ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== OCR FUNCTIONS ====================
def extract_id_number(lines):
    POSSIBLE_LABELS = ["reg no", "registration no", "reg. no", "regno", "regn no", "regn.", "reg"]
    for line in lines:
        if any(label in line.lower() for label in POSSIBLE_LABELS):
            match = re.search(r"reg(?:istration)?\.?\s*no[:\s]*([A-Z0-9]{6,})", line, re.IGNORECASE)
            if match:
                return match.group(1)
    return "Not found"

def save_to_database(data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    visit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO visitors (student_id, name, department, visit_time)
    VALUES (?, ?, ?, ?)
""", (data['reg_no'], data['name'], data['department'], visit_time))
    conn.commit()
    conn.close()

def speak_message(msg):
    engine = pyttsx3.init()
    engine.say(msg)
    engine.runAndWait()

def resume_capture():
    global capture_active
    capture_active = True

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
        words = line.split()
        if 1 < len(words) <= 4 and all(w.isalpha() or '.' in w for w in words):
            name = line.strip().title()
            break

    latest_ocr_data = {
        "name": name,
        "reg_no": reg_no,
        "department": department
    }

    # If all fields are found and not already saved
   # Remove auto DB save from process_frame_for_ocr and just pause scanning:
    if name != "Not found" and reg_no != "Not found" and department != "Not found":
        with lock:
            if last_saved_reg_no != reg_no:
                last_saved_reg_no = reg_no
                speak_message("Details captured successfully")
                capture_active = False  # Stop scanning until user decides


# ==================== VIDEO STREAM GENERATOR ====================
def gen_frames():
    cap = cv2.VideoCapture(0)
    while True:
        success, frame = cap.read()
        if not success:
            break

        process_frame_for_ocr(frame)

        # Draw rectangle for visual aid
        h, w, _ = frame.shape
        top = int(h * 0.55)
        bottom = int(h * 0.95)
        left = int(w * 0.15)
        right = int(w * 0.85)
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

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
    print("📂 Reading from DB file:", os.path.abspath(DB_PATH))
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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

# >>> NEW <<<  --- Manual resume endpoint
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
    print("✅ /save_visitor endpoint CALLED")
    data = request.get_json()
    print("📦 Data received:", data)
    print("Saving visitor data:", data)  # debug print
    print(f"Database path: {DB_PATH}")

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


# ==================== MAIN ====================
if __name__ == '__main__':
    app.run(debug=True)
