from pathlib import Path

p = Path("scripts/router_dispatch_codex.py")
code = p.read_text()

old = """    r_task_id = result.get("task_id")
    r_status = result.get("status")
    r_provenance = result.get("provenance", {})"""

new = """    r_task_id = result.get("task_id")
    r_status = result.get("status")
    r_payload = result.get("payload", {})
    if r_payload.get("verdict") == "BLOCKED_RATE_LIMIT":
        print("[FAIL] Codex rate limited!")
        sys.exit(3)
    r_provenance = result.get("provenance", {})"""

code = code.replace(old, new)
p.write_text(code)
print("Patched.")
