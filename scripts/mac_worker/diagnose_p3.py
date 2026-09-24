import requests

HEADERS = {'Authorization': 'Bearer 321606503a874d39b50f6137e3321b7f', 'Content-Type': 'application/json'}
res = requests.get("http://127.0.0.1:8080/workers", headers=HEADERS)
workers = res.json()

windows_workers = [w for w, data in workers.items() if "windows" in data.get("capabilities", []) or data.get("platform") == "windows"]

if not windows_workers:
    print("CAUSAL BLOCKER IDENTIFIED: No Windows workers are registered.")
    print("P3 'Echter Betriebsnachweis' requires >= 2 real workers (Mac + Windows).")
    print("Without a Windows worker, tasks with target_capability='windows' will remain QUEUED forever.")
else:
    print(f"Windows workers found: {windows_workers}")
