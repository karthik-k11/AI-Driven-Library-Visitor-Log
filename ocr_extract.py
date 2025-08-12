import cv2
import pytesseract
import re
import difflib
import pyttsx3
from datetime import datetime
import sqlite3

# Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Valid department list
DEPARTMENT_KEYWORDS = [
    "MCA", "MBA", "BCA", "BBA", "BTECH", "MTECH", "M.Com", "B.Sc", "M.Sc",
    "CSE", "ECE", "student", "engineer", "developer", "librarian", "faculty"
]

IGNORE_KEYWORDS = ["college", "institute", "principal", "validity", "year", "batch"]

# Extract Reg No from label
def extract_id_number(lines):
    POSSIBLE_LABELS = ["reg no", "registration no", "reg. no", "regno", "regn no", "regn.", "reg"]
    for line in lines:
        if any(label in line.lower() for label in POSSIBLE_LABELS):
            match = re.search(r"reg(?:istration)?\.?\s*no[:\s]*([A-Z0-9]{6,})", line, re.IGNORECASE)
            if match:
                return match.group(1)
    return "Not found"

# Start webcam
cap = cv2.VideoCapture(0)
print("📡 Scanning for ID card... Show the card to the camera.")

frame_box = None
extracted = False

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
    frame_box = (left, top, right, bottom)

    # Draw rectangle
    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
    cv2.putText(frame, "Scanning for ID card fields...", (left, top - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    cv2.imshow("ID Card Scanner", frame)
    cv2.moveWindow("ID Card Scanner", 10, 20)

    # Crop and preprocess
    cropped = frame[top:bottom, left:right]
    gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, None, fx=1.8, fy=1.8, interpolation=cv2.INTER_CUBIC)

    # OCR
    ocr_text = pytesseract.image_to_string(resized, config="--oem 3 --psm 6")
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
    name, reg_no, department = "Not found", "Not found", "Not found"

    # Reg No
    reg_no = extract_id_number(lines)

    # Department
    for line in lines:
        for dept in DEPARTMENT_KEYWORDS:
            if dept.lower() in line.lower():
                department = dept.upper()
                break
        if department != "Not found":
            break

    # Name
    for line in lines:
        if any(word in line.lower() for word in IGNORE_KEYWORDS):
            continue
        words = line.split()
        if 1 < len(words) <= 4 and all(w.isalpha() or '.' in w for w in words):
            name = line.strip().title()
            break

    # Validate
    if len(reg_no) == 14 and department.strip().lower() == "mca" and name != "Not found":
        engine = pyttsx3.init()
        engine.say("Details captured successfully.")
        engine.runAndWait()

    # ✅ Save to SQLite
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



    # ESC to exit manually
    if cv2.waitKey(1) & 0xFF == 27:
        print("❌ ESC pressed. Exiting.")
        break

cap.release()
cv2.destroyAllWindows()

# Final timestamp
visit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Output
print("\n📝 OCR Text:\n" + "-" * 30)
print(ocr_text)

print("\n--- ✅ Extracted Fields ---")
print("Name       :", name)
print("ID Number  :", reg_no)
print("Department :", department)
print("Visit Time :", visit_time)

if not extracted:
    print("⚠️  Missing critical data. Please adjust card or lighting.")