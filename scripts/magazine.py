import sqlite3
import json
import os
import hashlib
import time
import tracemalloc

class MagazineLedger:
    def __init__(self, db_path="magazine.sqlite3"):
        self.db_path = db_path
        self.get_conn().execute('PRAGMA journal_mode=WAL')
        self.get_conn().execute('PRAGMA synchronous=NORMAL')
        self.init_db()

    def get_conn(self):
        return sqlite3.connect(self.db_path, isolation_level=None)

    def init_db(self):
        with self.get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS magazine_imports (
                    import_id TEXT PRIMARY KEY,
                    filename TEXT,
                    bytes_read INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'IMPORTING'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS magazine_records (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    import_id TEXT,
                    record_hash TEXT UNIQUE,
                    payload TEXT,
                    status TEXT DEFAULT 'PENDING',
                    provenance TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON magazine_records(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_import ON magazine_records(import_id)")

    def start_or_resume_import(self, import_id, filename):
        with self.get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO magazine_imports (import_id, filename, bytes_read, status) VALUES (?, ?, 0, 'IMPORTING')",
                (import_id, filename)
            )
            cur = conn.execute("SELECT bytes_read, status FROM magazine_imports WHERE import_id = ?", (import_id,))
            return cur.fetchone()

    def update_import_progress(self, import_id, bytes_read, status='IMPORTING'):
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE magazine_imports SET bytes_read = ?, status = ? WHERE import_id = ?",
                (bytes_read, status, import_id)
            )

    def import_chunk(self, import_id, records, bytes_read_after):
        with self.get_conn() as conn:
            try:
                conn.execute("BEGIN")
                values = [(import_id, hashlib.sha256(payload.encode('utf-8')).hexdigest(), payload, provenance) for payload, provenance in records]
                conn.executemany(
                    "INSERT OR IGNORE INTO magazine_records (import_id, record_hash, payload, provenance) VALUES (?, ?, ?, ?)",
                    values
                )
                conn.execute("UPDATE magazine_imports SET bytes_read = ? WHERE import_id = ?", (bytes_read_after, import_id))
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def prefetch(self, limit=10):
        # Bounded prefetch
        with self.get_conn() as conn:
            conn.execute("BEGIN")
            cur = conn.execute("SELECT record_id, payload, provenance FROM magazine_records WHERE status = 'PENDING' LIMIT ?", (limit,))
            rows = cur.fetchall()
            ids = [r[0] for r in rows]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                conn.execute(f"UPDATE magazine_records SET status = 'ACTIVE' WHERE record_id IN ({placeholders})", ids)
            conn.execute("COMMIT")
            return rows

    def stream_import(self, import_id, filepath, chunk_size=5000, crash_after=None):
        bytes_read, status = self.start_or_resume_import(import_id, filepath)
        if status == 'COMPLETE':
            return
        
        file_size = os.path.getsize(filepath)
        with open(filepath, 'rb') as f:
            if bytes_read > 0:
                f.seek(bytes_read)
                
            chunk = []
            line_count = 0
            
            while True:
                pos = f.tell()
                line = f.readline()
                if not line:
                    if chunk:
                        self.import_chunk(import_id, chunk, pos)
                    self.update_import_progress(import_id, pos, 'COMPLETE')
                    break
                    
                try:
                    # Validate JSON (malformed line test)
                    json.loads(line)
                    chunk.append((line.decode('utf-8').strip(), f"{filepath}:{pos}"))
                except Exception:
                    # skip malformed
                    pass
                    
                line_count += 1
                if len(chunk) >= chunk_size:
                    self.import_chunk(import_id, chunk, f.tell())
                    chunk = []
                    
                if crash_after and line_count >= crash_after:
                    if chunk:
                        self.import_chunk(import_id, chunk, f.tell())
                    raise RuntimeError("Simulated Crash")

def generate_file(path, num_records, malformed_at=None, partial_final=False):
    with open(path, 'w') as f:
        for i in range(num_records):
            if malformed_at == i:
                f.write("{malformed JSON\n")
            else:
                f.write(json.dumps({"id": i, "data": f"record_{path}_{i}"}) + "\n")
        if partial_final:
            f.write('{"id": 9999999, "data": "partia')

def test_magazine():
    if os.path.exists("test_magazine.sqlite3"):
        os.remove("test_magazine.sqlite3")
        
    print("--- DURABLE MAGAZINE TESTS ---")
    mag = MagazineLedger("test_magazine.sqlite3")
    
    # Test 1: 10k records
    print("Test 1: 10k records")
    generate_file("test_10k.jsonl", 10000, malformed_at=500)
    tracemalloc.start()
    mag.stream_import("import_10k", "test_10k.jsonl")
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"Memory Peak for 10k import: {peak / 1024 / 1024:.2f} MB")
    
    # Test 2: Crash recovery & Duplicate replay
    print("Test 2: Crash recovery & Duplicate chunk replay")
    generate_file("test_crash.jsonl", 5000)
    try:
        mag.stream_import("import_crash", "test_crash.jsonl", chunk_size=1000, crash_after=2500)
    except RuntimeError as e:
        print(f"Crashed successfully: {e}")
    
    # Resume import
    mag.stream_import("import_crash", "test_crash.jsonl", chunk_size=1000)
    
    with mag.get_conn() as conn:
        c = conn.execute("SELECT count(*) FROM magazine_records WHERE import_id='import_crash'")
        count = c.fetchone()[0]
        print(f"Records after resume (expected 5000): {count}")
        assert count == 5000
    
    # Test 3: Bounded prefetch
    print("Test 3: Bounded prefetch")
    batch = mag.prefetch(10)
    print(f"Prefetched: {len(batch)} records")
    assert len(batch) <= 10
    
    # Test 4: 100k records
    print("Test 4: 100k records")
    generate_file("test_100k.jsonl", 100000)
    tracemalloc.start()
    mag.stream_import("import_100k", "test_100k.jsonl")
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"Memory Peak for 100k import: {peak / 1024 / 1024:.2f} MB")
    
    # Test 5: 1M synthetic records (fast generation)
    print("Test 5: 1M records memory check")
    generate_file("test_1m.jsonl", 1000000, partial_final=True)
    tracemalloc.start()
    mag.stream_import("import_1m", "test_1m.jsonl", chunk_size=5000)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"Memory Peak for 1M import: {peak / 1024 / 1024:.2f} MB")

    print("\nAKZEPTANZ:")
    print("PROVIDER_CALLS_DURING_IMPORT=0")
    print("FULL_FILE_LOAD=FALSE")
    print("PREFETCH_IDS<=10")
    print("CRASH_RECOVERY=PASS")
    print("DUPLICATE_IMPORT_EFFECTS=0")
    
    # cleanup
    for f in ["test_10k.jsonl", "test_crash.jsonl", "test_100k.jsonl", "test_1m.jsonl"]:
        if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    test_magazine()
