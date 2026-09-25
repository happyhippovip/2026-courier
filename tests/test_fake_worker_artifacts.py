"""Contract: fake_worker artifact confinement (trust boundary).

A malicious instruction must not write outside its workspace: the
worker exits 4, writes neither the escape file nor a result. A legit
artifact is still written with a SUCCESS result. Drives the real
`cannon.fake_worker` subprocess; scratch lives under storage ROOT
(owned-confinement) and is always removed.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app.cannon import storage

APP_DIR = Path(__file__).resolve().parent.parent / "app"
CONTRACT_SRC = (
    "def verify_result(task, raw, workspace):\n"
    "    return dict(raw)\n"
)


@pytest.fixture
def scratch():
    root = Path(storage.__file__).resolve().parents[2]
    assert Path(storage.ROOT) == root
    box = root / f".tmp-fw-test-{os.getpid()}"
    (box / "ws").mkdir(parents=True)
    (box / "contract.py").write_text(CONTRACT_SRC, encoding="utf-8")
    yield box
    shutil.rmtree(box, ignore_errors=True)


def run_worker(box: Path, artifacts, instruction="hello") -> subprocess.CompletedProcess:
    request = {
        "task": {"goal_id": "g", "task_id": "t1", "attempt_id": "a1",
                 "dispatch_id": "d1", "execution_ref": "e1",
                 "worker_id": "w1", "instruction": instruction,
                 "artifacts": artifacts},
        "mode": "SUCCESS", "delay": 0,
        "workspace": str(box / "ws"),
        "contract": str(box / "contract.py"),
        "result": str(box / "result.json"),
        "events": str(box / "event.json"),
    }
    (box / "request.json").write_text(json.dumps(request), encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(APP_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "cannon.fake_worker", str(box / "request.json")],
        input=b"GO\n", capture_output=True, timeout=60, env=env, cwd=str(box))


def test_escape_artifact_blocked_without_result(scratch):
    proc = run_worker(scratch, ["../escape.txt"])
    assert proc.returncode == 4
    assert not (scratch.parent / "escape.txt").exists()
    assert not (scratch / "ws" / "escape.txt").exists()
    assert not (scratch / "result.json").exists()


def test_legit_artifact_written_with_success_result(scratch):
    proc = run_worker(scratch, ["out.txt"], instruction="do it")
    assert proc.returncode == 0, proc.stderr.decode()[-500:]
    assert (scratch / "ws" / "out.txt").read_text(encoding="utf-8") == "do it\n"
    result = json.loads((scratch / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "SUCCESS"
    assert result["task_id"] == "t1"
