import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
process = subprocess.Popen(
    [sys.executable, str(ROOT / "app/server.py"), "--cannon-only", "--port", "8768"],
    cwd=str(ROOT), stderr=subprocess.PIPE
)
out, err = process.communicate()
print("ERR:", err.decode())
