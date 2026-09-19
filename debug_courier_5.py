from tests.test_antigravity_continuous import setup_ledger
import os
import subprocess
from pathlib import Path
import tempfile

courier_script = str(Path("scripts/courier_continue.py").resolve())

with tempfile.TemporaryDirectory() as tmp:
    ledger_path = Path(tmp) / "agent_handoff_ledger.json"
    setup_ledger(Path(tmp))
    
    env = os.environ.copy()
    env["MOCK_SHA"] = "0000000000000000000000000000000000000000"
    env["MOCK_LEDGER"] = str(ledger_path)
    env["COURIER_API_KEY"] = "test"
    env["COURIER_VERIFIER_API_KEY"] = "test"
    
    print("RUNNING")
    res = subprocess.run(["python3", courier_script, "--run", "--once"], env=env, capture_output=True, text=True, timeout=10)
    print("STDOUT:", res.stdout)
    print("STDERR:", res.stderr)
