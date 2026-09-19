import sqlite3
import threading
from scripts.magazine import MagazineLedger

def test_contention():
    mag = MagazineLedger("test_magazine.sqlite3")
    
    with mag.get_conn() as conn:
        conn.execute("DELETE FROM magazine_records")
        values = [('test', f'hash_{i}', f'payload_{i}', 'prov') for i in range(10)]
        conn.executemany("INSERT INTO magazine_records (import_id, record_hash, payload, provenance) VALUES (?, ?, ?, ?)", values)
        conn.execute("UPDATE magazine_records SET status = 'PENDING'")
        
    results = []
    barrier = threading.Barrier(2)
    def worker(wid):
        with mag.get_conn() as conn:
            barrier.wait()
            conn.execute("BEGIN")
            cur = conn.execute("SELECT record_id FROM magazine_records WHERE status = 'PENDING' LIMIT 5")
            rows = cur.fetchall()
            ids = [r[0] for r in rows]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                conn.execute(f"UPDATE magazine_records SET status = 'ACTIVE' WHERE record_id IN ({placeholders})", ids)
            try:
                conn.execute("COMMIT")
                results.append((wid, ids))
            except Exception as e:
                print(f"Worker {wid} failed: {e}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    for wid, fetched in results:
        print(f"Worker {wid} fetched: {fetched}")
        
test_contention()
