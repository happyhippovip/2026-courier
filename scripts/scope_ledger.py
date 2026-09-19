import sys
import sqlite3
import time
import uuid
import os

class ScopeLedger:
    def __init__(self, db_path="scope.sqlite3"):
        self.db_path = db_path
        self.get_conn().execute('PRAGMA journal_mode=WAL')
        self.get_conn().execute('PRAGMA synchronous=NORMAL')
        self.init_db()

    def get_conn(self):
        return sqlite3.connect(self.db_path, isolation_level=None)

    def init_db(self):
        with self.get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scope_leases (
                    lease_id TEXT PRIMARY KEY,
                    scope_id TEXT,
                    mode TEXT,
                    task_id TEXT,
                    execution_id TEXT,
                    worker_id TEXT,
                    fencing_token TEXT,
                    acquired_at REAL,
                    expires_at REAL
                )
            """)

    def _normalize_scope(self, scope_id):
        # Resolve symlinks and normalize to absolute path style
        s = os.path.realpath(scope_id)
        s = os.path.normpath(s)
        # On APFS/NTFS, case might not matter, but realpath returns the true case if exists.
        # If we assume case-insensitive, we could lower(), but let's just stick to realpath for now.
        if not s.startswith('/'):
            s = '/' + s
        return s.lower() if os.name == 'nt' or sys.platform == 'darwin' else s

    def _overlaps(self, s1, s2):
        if s1 == s2:
            return True
        if s1.startswith(s2 + '/') or s2.startswith(s1 + '/'):
            return True
        return False

    def acquire_lease(self, scope_id, mode, task_id, execution_id, worker_id, ttl=60.0):
        scope_id = self._normalize_scope(scope_id)
        now = time.time()
        
        with self.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                # Get active leases
                cur = conn.execute("SELECT lease_id, scope_id, mode FROM scope_leases WHERE expires_at > ?", (now,))
                active_leases = cur.fetchall()
                
                # Check overlaps
                for l_id, active_scope, active_mode in active_leases:
                    if self._overlaps(scope_id, active_scope):
                        if mode == 'WRITE' or active_mode == 'WRITE':
                            # Conflict!
                            conn.execute("ROLLBACK")
                            return None # Denied
                            
                # Grant lease
                lease_id = str(uuid.uuid4())
                fencing_token = str(uuid.uuid4())
                expires_at = now + ttl
                
                conn.execute("""
                    INSERT INTO scope_leases 
                    (lease_id, scope_id, mode, task_id, execution_id, worker_id, fencing_token, acquired_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (lease_id, scope_id, mode, task_id, execution_id, worker_id, fencing_token, now, expires_at))
                
                conn.execute("COMMIT")
                return {
                    "lease_id": lease_id,
                    "fencing_token": fencing_token,
                    "expires_at": expires_at
                }
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def verify_fencing_token(self, fencing_token):
        now = time.time()
        with self.get_conn() as conn:
            cur = conn.execute("SELECT expires_at FROM scope_leases WHERE fencing_token = ? AND expires_at > ?", (fencing_token, now))
            return cur.fetchone() is not None

    def reconcile_crashed_worker(self, worker_id):
        now = time.time()
        with self.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE scope_leases SET expires_at = ? WHERE worker_id = ? AND expires_at > ?", (now - 1, worker_id, now))
            conn.execute("COMMIT")

def test_scopes():
    if os.path.exists("test_scopes.sqlite3"):
        os.remove("test_scopes.sqlite3")
        
    ledger = ScopeLedger("test_scopes.sqlite3")
    
    # Test 1: A writes file X, B writes file X -> never at same time.
    l1 = ledger.acquire_lease("file_x", "WRITE", "t1", "e1", "w1")
    assert l1 is not None
    l2 = ledger.acquire_lease("file_x", "WRITE", "t2", "e2", "w2")
    assert l2 is None
    
    # Test 2: A writes dir /foo, B writes /foo/bar -> overlap
    l3 = ledger.acquire_lease("/foo", "WRITE", "t3", "e3", "w3")
    assert l3 is not None
    l4 = ledger.acquire_lease("/foo/bar", "WRITE", "t4", "e4", "w4")
    assert l4 is None
    
    # Test 3: A read-only /foo, B writes /foo
    l5 = ledger.acquire_lease("/bar", "READ", "t5", "e5", "w5")
    assert l5 is not None
    l6 = ledger.acquire_lease("/bar", "WRITE", "t6", "e6", "w6")
    assert l6 is None
    l7 = ledger.acquire_lease("/bar", "READ", "t7", "e7", "w7") # multiple reads allowed
    assert l7 is not None
    
    # Test 4: A lease expires, A arbeitet physisch noch, B claims -> B darf nicht ohne fencing/reconcile unsafe schreiben.
    l8 = ledger.acquire_lease("/baz", "WRITE", "t8", "e8", "w8", ttl=0.1)
    time.sleep(0.2)
    # A's lease expired. B can now claim it.
    l9 = ledger.acquire_lease("/baz", "WRITE", "t9", "e9", "w9")
    assert l9 is not None
    
    # A tries to write using its old fencing token
    assert ledger.verify_fencing_token(l8["fencing_token"]) == False
    assert ledger.verify_fencing_token(l9["fencing_token"]) == True
    
    print("AKZEPTANZ:")
    print("CONCURRENT_WRITERS_SAME_SCOPE=0")
    print("STALE_WRITER_ACCEPTED=0")
    
if __name__ == "__main__":
    test_scopes()
