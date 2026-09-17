import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ide_task_cleanup.sh"


def test_cleanup_watchdog_never_kills_unregistered_matching_process(tmp_path):
    unrelated = subprocess.Popen(
        ["python3", "-c", "import time; time.sleep(30)", "test_unowned.py"]
    )
    try:
        completed = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        assert completed.returncode == 0, completed.stderr
        assert "Audit complete" in completed.stdout
        time.sleep(0.1)
        assert unrelated.poll() is None
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=5)
