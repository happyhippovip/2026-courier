from pathlib import Path
import re

p = Path("scripts/router_dispatch_codex.py")
code = p.read_text()

# Fix dedupe_hash
code = code.replace("    scope_str = opp.allowed_scope[0] if opp.allowed_scope else \"C:\\Dev\\Windows-AI-OS\"", "    scope_str = opp.allowed_scope[0] if opp.allowed_scope else \"C:\\\\Dev\\\\Windows-AI-OS\"\n    dedupe_hash = opp.dedupe_hash if opp.dedupe_hash else hashlib.sha256(task_id.encode()).hexdigest()[:16]")

# Fix remaining hardcoded scope_str
code = code.replace("    scope_str = \"C:\\\\Dev\\\\Windows-AI-OS\"\n    authority = CanonicalAuthority()", "    authority = CanonicalAuthority()")

p.write_text(code)
print("Fixed.")
