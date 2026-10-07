"""L2 + L4 composition: controller accepts local_shell evidence via the real verifier."""

import hashlib

from courier_core.events import EventType
from courier_core.verification import adapter_verifier

from ctrl_helpers import make_controller, result_body, task_body


def test_local_shell_result_accepted_with_real_verifier(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    evidence = b"courier-local-shell-ctrl"
    (home / "out.txt").write_bytes(evidence)
    digest = hashlib.sha256(evidence).hexdigest()

    ctl = make_controller(home, verifier=adapter_verifier)
    try:
        _, body = ctl.create_task(task_body(
            adapter="local_shell",
            params={"command": ["true"], "write": "out.txt"},
        ))
        lease = ctl.claim({"worker_id": "w1"})
        ctl.start({"dispatch_id": lease["dispatch_id"]})
        ctl.result(result_body(lease["dispatch_id"], sha=digest))
        ctl.drain()
        accepted = [e for e in ctl.journal.events(task_id=body["task_id"])
                    if e.type is EventType.RESULT_ACCEPTED]
        assert len(accepted) == 1
        verifier = accepted[0].payload["verifier"]
        assert verifier["kind"] == "adapter"
        assert verifier["name"].startswith("adapters.local_shell.")
        assert ctl.journal.task(body["task_id"]).resolution == "verified"
    finally:
        ctl.stop()


def test_local_shell_wrong_hash_is_rejected(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "out.txt").write_bytes(b"real-bytes")
    ctl = make_controller(home, verifier=adapter_verifier)
    try:
        _, body = ctl.create_task(task_body(adapter="local_shell", params={"command": ["true"]}))
        lease = ctl.claim({"worker_id": "w1"})
        ctl.start({"dispatch_id": lease["dispatch_id"]})
        ctl.result(result_body(lease["dispatch_id"], sha=hashlib.sha256(b"wrong").hexdigest()))
        ctl.drain()
        rejected = [e for e in ctl.journal.events(task_id=body["task_id"])
                      if e.type is EventType.RESULT_REJECTED]
        assert len(rejected) == 1
        assert rejected[0].payload["verifier"]["kind"] == "adapter"
    finally:
        ctl.stop()
