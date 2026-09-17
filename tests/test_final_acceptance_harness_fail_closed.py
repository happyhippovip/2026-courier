import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from scripts.acceptance import run_final_acceptance


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


def test_opted_in_synthetic_harness_is_bounded_and_side_effect_free(tmp_path):
    env = os.environ.copy()
    env["COURIER_RUN_SYNTHETIC_ACCEPTANCE"] = "1"

    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "SYNTHETIC_TEST_ONLY=YES" in completed.stdout
    assert "PHYSICAL_ACCEPTANCE=NO" in completed.stdout
    assert "TESTS_RUN=59" in completed.stdout
    assert "PASS=59" in completed.stdout
    assert "FAIL=0" in completed.stdout
    assert completed.stdout.count("Running 10-task goal test...") == 1
    assert not (tmp_path / "acceptance_state.json").exists()


def test_synthetic_harness_kills_only_its_exact_hung_child():
    child = mock.Mock()
    child.poll.return_value = None
    child.wait.side_effect = [subprocess.TimeoutExpired("child", 10), 0]

    run_final_acceptance.stop_server(child)

    child.terminate.assert_called_once_with()
    child.kill.assert_called_once_with()
    assert child.wait.call_args_list == [mock.call(timeout=10), mock.call(timeout=5)]
