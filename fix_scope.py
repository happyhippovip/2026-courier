import sys
content = open("scripts/scope_ledger.py").read()

import re

# Fix _normalize_scope
new_func = """
    def _normalize_scope(self, scope_id):
        # Resolve symlinks and normalize to absolute path style
        s = os.path.realpath(scope_id)
        s = os.path.normpath(s)
        # On APFS/NTFS, case might not matter, but realpath returns the true case if exists.
        # If we assume case-insensitive, we could lower(), but let's just stick to realpath for now.
        if not s.startswith('/'):
            s = '/' + s
        return s.lower() if os.name == 'nt' or sys.platform == 'darwin' else s
"""

content = re.sub(r'    def _normalize_scope.*?return s', new_func.strip('\n'), content, flags=re.DOTALL)
open("scripts/scope_ledger.py", "w").write("import sys\n" + content)
