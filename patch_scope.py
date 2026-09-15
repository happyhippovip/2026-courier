import sys

with open('scripts/router_dispatch_codex.py', 'r') as f:
    code = f.read()

code = code.replace('scope_str = opp.allowed_scope[0] if opp.allowed_scope else "C:\\\\Dev\\\\Windows-AI-OS"', 'scope_str = opp.allowed_scope[0].strip().rstrip("/") if opp.allowed_scope else "C:\\\\Dev\\\\Windows-AI-OS"')

with open('scripts/router_dispatch_codex.py', 'w') as f:
    f.write(code)
