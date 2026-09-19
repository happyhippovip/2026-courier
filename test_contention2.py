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
    def worker(wid):
        try:
            rows = mag.prefetch(5)
            if rows:
                results.append((wid, [r[0] for r in rows]))
        except Exception:
            pass

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    for wid, fetched in results:
        print(f"Worker {wid} fetched: {fetched}")
        
test_contention()
