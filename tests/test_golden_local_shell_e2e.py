"""Golden-path E2E for the local_shell adapter (L1 extension, outside tests/golden ratchet).

Exercises controller + worker + real local_shell verifier when the L3 worker
allowlists ``local_shell``. Skips on integration until that allowlist lands
(for example PR #141); does not change EXPECTED_TOTAL in check_golden_skips.py.
"""

import json
import sys
from pathlib import Path

import pytest

_GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
if str(_GOLDEN_DIR) not in sys.path:
    sys.path.insert(0, str(_GOLDEN_DIR))

from golden_harness import (  # noqa: E402
    LOCAL_SHELL_SHA256,
    Courier,
    missing_modules,
    pids_alive,
)
from courier_worker import adapter_bridge  # noqa: E402

pytestmark = [
    pytest.mark.skipif(bool(missing_modules()), reason="golden v1 modules missing"),
    pytest.mark.skipif(
        "local_shell" not in adapter_bridge.ADAPTERS,
        reason="worker has not allowlisted local_shell adapter yet",
    ),
]


@pytest.fixture
def courier(tmp_path):
    home = tmp_path / "courier_home"
    logs = tmp_path / "logs"
    home.mkdir()
    logs.mkdir()
    instance = Courier(home, logs)
    yield instance
    instance.close()


def test_local_shell_golden_lifecycle(courier):
    courier.start_controller()
    courier.start_worker()

    task_id = courier.make_local_shell_task()
    courier.wait_event(task_id, "TASK_COMPLETE", timeout=60)

    events = courier.task_events(task_id)
    types = [e["type"] for e in events if e["type"] != "TASK_PROGRESS"]
    assert types == [
        "TASK_CREATED",
        "TASK_CLAIMED",
        "TASK_STARTED",
        "RESULT_READY",
        "RESULT_ACCEPTED",
        "TASK_COMPLETE",
    ]
    ready = next(e for e in events if e["type"] == "RESULT_READY")
    artifacts = json.loads(ready["payload"])["artifacts"]
    assert any(a.get("sha256") == LOCAL_SHELL_SHA256 for a in artifacts), artifacts

    worker_tree = [courier.worker.pid, *courier.worker_descendants()]
    courier.stop_worker_graceful()
    courier.stop_controller_graceful()
    assert pids_alive([*worker_tree, courier.controller.pid]) == []
    assert courier.outbox_files() == []
