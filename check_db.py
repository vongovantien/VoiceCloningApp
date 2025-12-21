import sqlite3
conn = sqlite3.connect('app.db')
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print("Tables:", tables)

# Check stories
try:
    stories = conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
    print(f"Stories count: {stories}")
except Exception as e:
    print(f"Stories error: {e}")

# Check categories
try:
    cats = conn.execute("SELECT * FROM story_categories").fetchall()
    print(f"Categories: {cats}")
except Exception as e:
    print(f"Categories error: {e}")

conn.close()
