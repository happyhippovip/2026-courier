from tests.test_antigravity_continuous import setup_ledger
import tempfile
from pathlib import Path
import os
os.environ["COURIER_API_KEY"] = "test-secret"
os.environ["COURIER_VERIFIER_API_KEY"] = "verifier-secret"
with tempfile.TemporaryDirectory() as tmp:
    setup_ledger(Path(tmp))
    print("SUCCESS")
