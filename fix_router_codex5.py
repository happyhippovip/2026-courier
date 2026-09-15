from pathlib import Path
import re

p = Path("scripts/router_dispatch_codex.py")
code = p.read_text()

# Fix the rest of the file
code = code.replace('"project_path": "C:\\\\Dev\\\\Windows-AI-OS",', '"project_path": scope_str,')
code = code.replace('"scope": ["C:\\\\Dev\\\\Windows-AI-OS"],', '"scope": opp.allowed_scope,')
code = code.replace('"allowed_scope": ["C:\\\\Dev\\\\Windows-AI-OS"],', '"allowed_scope": opp.allowed_scope,')

p.write_text(code)
print("Re-patched!")
