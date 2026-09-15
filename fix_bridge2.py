from pathlib import Path

p = Path("scripts/run_codex_bridge.py")
code = p.read_text()

code = code.replace("""    if isinstance(lease, dict) and len(scope) == 1 and lease.get("scope") != scope[0]:
        errors.append("LEASE_SCOPE_NOT_ENVELOPE_SCOPE")""", """    if isinstance(lease, dict) and lease.get("scope") not in scope:
        errors.append("LEASE_SCOPE_NOT_ENVELOPE_SCOPE")""")

p.write_text(code)
print("Bridge patched 2.")
