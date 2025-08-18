import sqlite3

conn = sqlite3.connect("library_visitors.db")
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS visitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    name TEXT NOT NULL,
    department TEXT NOT NUll, 
    visit_time TEXT NOT NULL,
)
''')

conn.commit()
conn.close()

print(" visitors table created successfully!")
