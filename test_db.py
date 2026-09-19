import sqlite3
conn = sqlite3.connect("test_magazine.sqlite3")
cur = conn.cursor()
cur.execute("SELECT count(*), import_id FROM magazine_records GROUP BY import_id")
print("Counts:", cur.fetchall())
cur.execute("SELECT * FROM magazine_imports")
print("Imports:", cur.fetchall())
