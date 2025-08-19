import sqlite3

# Connect to SQLite database (this will create the file if it doesn’t exist)
conn = sqlite3.connect("library_visitors.db")
cursor = conn.cursor()

# ================= Visitors Table =================
cursor.execute('''
CREATE TABLE IF NOT EXISTS visitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    name TEXT NOT NULL,
    department TEXT NOT NULL, 
    visit_time TEXT NOT NULL
)
''')

# ================= Users Table =================
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)
''')

# Insert default librarian account (if not already inserted)
cursor.execute("SELECT * FROM users WHERE username = ?", ("kle_library",))
if not cursor.fetchone():
    cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                   ("kle_library", "admin123"))

# Save changes and close
conn.commit()
conn.close()

print("Database and tables created successfully!")
