import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "acceptance" / "run_final_acceptance.py"


def test_synthetic_acceptance_harness_refuses_default_execution(tmp_path):
    env = os.environ.copy()
    env.pop("COURIER_RUN_SYNTHETIC_ACCEPTANCE", None)

    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 2
    assert "SYNTHETIC_TEST_ONLY=YES" in completed.stdout
    assert "PHYSICAL_ACCEPTANCE=NO" in completed.stdout
    assert "TASKS_COMPLETED=" not in completed.stdout
    assert "CLEAN_IDLE=YES" not in completed.stdout
    assert not (tmp_path / "acceptance_state.json").exists()
