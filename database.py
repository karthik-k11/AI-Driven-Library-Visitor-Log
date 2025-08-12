import sqlite3

def init_db():
    conn = sqlite3.connect('visitors.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS visitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            name TEXT,
            timestamp TEXT,
            face_match_status TEXT,
            image_path TEXT
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()