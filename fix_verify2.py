import sys
content = open("scripts/scope_ledger.py").read()
import re
new_func = """
    def verify_fencing_token(self, fencing_token):
        now = time.time()
        
        with self.get_conn() as conn:
            cur = conn.execute("SELECT expires_at FROM scope_leases WHERE fencing_token = ? AND expires_at > ?", (fencing_token, now))
            return cur.fetchone() is not None
"""
# Strip but preserve the 4 spaces indent
content = re.sub(r'    def verify_fencing_token\(self, scope_id, fencing_token\):.*?return active_token == fencing_token', new_func.strip('\n'), content, flags=re.DOTALL)
open("scripts/scope_ledger.py", "w").write(content)
