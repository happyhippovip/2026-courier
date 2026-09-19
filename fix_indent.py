import sys
content = open("scripts/magazine.py").read()
import re
new_func = """
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
"""
# Strip but preserve the 4 spaces indent
content = re.sub(r'def import_chunk\(.*?raise', new_func.strip() + '\n', content, flags=re.DOTALL)
open("scripts/magazine.py", "w").write(content)
