import sqlite3

conn = sqlite3.connect("library_visitors.db")
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS visitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    name TEXT NOT NULL,
    visit_time TEXT NOT NULL,
    image_path TEXT,
    face_match_status TEXT
)
''')

conn.commit()
conn.close()

print(" visitors table created successfully!")
