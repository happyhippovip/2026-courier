from __future__ import annotations

import json
from pathlib import Path
import threading
import urllib.request

import pytest

import scripts.muse_bench_server as mbs


def test_ensure_dirs_and_checkpoint(tmp_path: Path):
    work_dir = tmp_path / "muse_work"
    mbs.ensure_dirs(work_dir)
    assert (work_dir / "results").exists()
    assert (work_dir / "lease").exists()
    cp = work_dir / "checkpoint.json"
    assert cp.exists()
    data = json.loads(cp.read_text(encoding="utf-8"))
    assert data["concurrency"] == 1


def test_queue_append_and_claim_lifecycle(tmp_path: Path):
    work_dir = tmp_path / "muse_work"
    mbs.ensure_dirs(work_dir)

    # 1. Empty queue
    assert mbs.read_queue(work_dir) == []

    # 2. Append task
    envelope = {
        "slot": "SLOT-1",
        "template_id": "T1",
        "inputs": {"arg": "val"},
        "prompt": "Test prompt",
    }
    rec = mbs.append_task(envelope, work_dir=work_dir)
    assert rec["state"] == "QUEUED"
    assert rec["task_id"].startswith("muse-")

    tasks = mbs.read_queue(work_dir)
    assert len(tasks) == 1
    assert tasks[0]["task_id"] == rec["task_id"]

    # 3. Claim task
    claimed = mbs.claim_task("runner-1", work_dir=work_dir)
    assert claimed is not None
    assert claimed["task_id"] == rec["task_id"]

    # 4. Second runner cannot claim concurrently
    claimed2 = mbs.claim_task("runner-2", work_dir=work_dir)
    assert claimed2 is None

    # 5. Release lease
    released = mbs.release_lease(work_dir=work_dir)
    assert released is True

    # 6. Now runner-2 can acquire lease
    claimed3 = mbs.claim_task("runner-2", work_dir=work_dir)
    assert claimed3 is not None
    assert claimed3["task_id"] == rec["task_id"]


def test_http_handler_endpoints(tmp_path: Path):
    work_dir = tmp_path / "muse_work"
    studio_dir = tmp_path / "studio"
    mbs.ensure_dirs(work_dir)
    studio_dir.mkdir(parents=True, exist_ok=True)
    (studio_dir / "muse-gallery.json").write_text(json.dumps([{"id": "gal-1"}]), encoding="utf-8")

    handler_cls = mbs.create_handler_class(work_dir=work_dir, studio_dir=studio_dir)
    import http.server
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        # 1. GET /api/muse/gallery
        req = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/muse/gallery")
        gal_data = json.loads(req.read().decode("utf-8"))
        assert len(gal_data) == 1
        assert gal_data[0]["id"] == "gal-1"

        # 2. POST /api/muse/queue
        post_data = json.dumps({"slot": "TEST", "prompt": "Hello"}).encode("utf-8")
        req2 = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/muse/queue",
            data=post_data,
            headers={"Content-Type": "application/json"},
        )
        resp2 = urllib.request.urlopen(req2)
        q_resp = json.loads(resp2.read().decode("utf-8"))
        assert q_resp["ok"] is True
        assert q_resp["task"]["slot"] == "TEST"

        # 3. GET /api/muse/state
        req3 = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/muse/state")
        state_resp = json.loads(req3.read().decode("utf-8"))
        assert len(state_resp["queue"]) == 1

        # 4. POST /api/muse/claim
        claim_data = json.dumps({"runner_id": "r1"}).encode("utf-8")
        req4 = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/muse/claim",
            data=claim_data,
            headers={"Content-Type": "application/json"},
        )
        resp4 = urllib.request.urlopen(req4)
        c_resp = json.loads(resp4.read().decode("utf-8"))
        assert c_resp["ok"] is True
        assert c_resp["task"]["slot"] == "TEST"
    finally:
        server.shutdown()
        server.server_close()


def test_main_cli_status(tmp_path: Path, capsys):
    work_dir = tmp_path / "muse_work"
    code = mbs.main(["--status", "--work-dir", str(work_dir), "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["queue_len"] == 0
