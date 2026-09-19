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
# Need to update test cases as well
content = re.sub(r'    def verify_fencing_token.*?return active_token == fencing_token', new_func.strip(), content, flags=re.DOTALL)
content = content.replace('ledger.verify_fencing_token("/baz", l8["fencing_token"])', 'ledger.verify_fencing_token(l8["fencing_token"])')
content = content.replace('ledger.verify_fencing_token("/baz", l9["fencing_token"])', 'ledger.verify_fencing_token(l9["fencing_token"])')
open("scripts/scope_ledger.py", "w").write(content)
