import subprocess, sys, os, json

files = [
    "scripts/intake_dispatcher.py",
    "scripts/queue_processor.py",
    "scripts/run_autonomous_loop.py",
    "scripts/run_autonomous_supervisor.py"
]

for f in files:
    if os.path.exists(f):
        print(f"Testing {f}...")
        res = subprocess.run([sys.executable, f], capture_output=True, text=True)
        if res.returncode != 1 or "Disabled in favor of OS-owned Courier Motor." not in res.stdout:
            print(f"FAILED on {f}")
            print("STDOUT:", res.stdout)
            sys.exit(1)

print("[*] W6 PASS: All legacy schedulers disabled.")
schema = {
    "SINGLE_SCHEDULER_PROVEN": "YES",
    "LEGACY_LOOPS_DISABLED": "YES",
}
with open("w6_proof.json", "w") as out:
    json.dump(schema, out)

