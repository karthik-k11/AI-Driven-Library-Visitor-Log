import sqlite3

# Connect to the database
conn = sqlite3.connect("library_visitors.db")
cursor = conn.cursor()

# Delete all rows from the visitors table
cursor.execute("DELETE FROM visitors")

# Commit changes and close connection
conn.commit()
conn.close()

print("✅ All records deleted successfully.")
