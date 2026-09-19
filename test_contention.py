import sqlite3
import threading
from scripts.magazine import MagazineLedger

def test_contention():
    mag = MagazineLedger("test_magazine.sqlite3")
    
    # insert 100 records
    with mag.get_conn() as conn:
        conn.execute("DELETE FROM magazine_records")
        values = [('test', f'hash_{i}', f'payload_{i}', 'prov') for i in range(100)]
        conn.executemany("INSERT INTO magazine_records (import_id, record_hash, payload, provenance) VALUES (?, ?, ?, ?)", values)
        conn.execute("UPDATE magazine_records SET status = 'PENDING'")
        
    errors = []
    def worker():
        try:
            mag.prefetch(10)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    print(f"Errors: {len(errors)}")
    for e in errors:
        print(e)
        
test_contention()
