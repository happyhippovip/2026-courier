import subprocess
from pathlib import Path

def test_ide_task_cleanup_runs_without_error(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(["bash", str(root / "scripts" / "ide_task_cleanup.sh")], capture_output=True, text=True)
    assert result.returncode == 0
    assert "ps: etimes: keyword not found" not in result.stderr
