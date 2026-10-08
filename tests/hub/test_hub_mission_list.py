"""L5 hub mission list (pool item P8): read-only view over receipt_read_model.

No provider, no controller, no writes: the bridge file and courier.db are
fixtures, and every test asserts the home directory is byte-identical after.
"""

import json
import os
import sqlite3
import threading
from pathlib import Path

import requests

os.environ["NO_PROXY"] = "*"

_orig_request = requests.Session.request


def _no_proxy_request(self, method, url, **kwargs):
    kwargs.setdefault("proxies", {"http": None, "https": None})
    return _orig_request(self, method, url, **kwargs)


requests.Session.request = _no_proxy_request

from courier_hub.server import Hub, HubServer  # noqa: E402


def _mission(task_id, status, when, goal="goal.missions.1", result=None):
    return {
        "task_id": task_id,
        "claim_event_id": "claim-" + task_id,
        "accepted_result_id": result,
        "status": status,
        "evidence_ref": "task_id=" + task_id,
        "goal_id": goal,
        "updated_at": when,
    }


def _write_bridge(home: Path, missions):
    home.mkdir(parents=True, exist_ok=True)
    (home / "ledger_bridge_state.json").write_text(
        json.dumps({"missions": missions}), encoding="utf-8")


def _write_results(home: Path, rows):
    home.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(home / "courier.db")
    conn.execute(
        "CREATE TABLE events (seq INTEGER PRIMARY KEY, type TEXT, task_id TEXT, "
        "attempt INTEGER, dispatch_id TEXT, result_id TEXT, ts_utc TEXT, payload TEXT)"
    )
    conn.executemany(
        "INSERT INTO events (type, task_id, attempt, dispatch_id, result_id, ts_utc, payload) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    _write_bridge(home, {
        "B": _mission("task-b", "BLOCKED", "2026-10-08T02:00:00Z"),
        "A": _mission("task-a", "FINAL_DONE", "2026-10-08T01:00:00Z", result="result-a"),
        "C": _mission("task-c", "ERROR", "2026-10-08T03:00:00Z", goal="goal.other"),
    })
    _write_results(home, [
        ("RESULT_ACCEPTED", "task-a", 1, "dsp-a", "result-a", "2026-10-08T01:00:01Z",
         json.dumps({"outcome": "success"})),
    ])
    return home


def _snapshot(home: Path):
    return {path.name: path.read_bytes() for path in sorted(home.iterdir())}


def test_mission_list_returns_sorted_receipts_and_writes_nothing(tmp_path):
    home = _home(tmp_path)
    before = _snapshot(home)
    view = Hub(home, "http://127.0.0.1:9", actor="desktop:tester").mission_list()
    assert view["truth"] == "ok"
    assert view["readable"] is True
    assert [item["task_id"] for item in view["receipts"]] == ["task-a", "task-b", "task-c"]
    assert view["receipts"][0]["result"]["result_id"] == "result-a"
    assert view["receipts"][1]["result"] is None
    assert isinstance(view["read_at"], str)
    assert _snapshot(home) == before


def test_mission_list_filters_and_invalid_window(tmp_path):
    hub = Hub(_home(tmp_path), "http://127.0.0.1:9", actor="desktop:tester")
    assert [item["task_id"] for item in hub.mission_list(status="BLOCKED")["receipts"]] == ["task-b"]
    assert [item["task_id"] for item in hub.mission_list(goal_id="goal.other")["receipts"]] == ["task-c"]
    window = hub.mission_list(since="2026-10-08T01:30:00Z", until="2026-10-08T02:30:00Z")
    assert [item["task_id"] for item in window["receipts"]] == ["task-b"]
    bad = hub.mission_list(since="not-a-time")
    assert bad["filter"] == "INVALID" and bad["receipts"] == []


def test_mission_list_unreadable_home_is_flagged(tmp_path):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    (home / "ledger_bridge_state.json").write_bytes(b"{broken")
    view = Hub(home, "http://127.0.0.1:9", actor="desktop:tester").mission_list()
    assert view["readable"] is False
    assert view["truth"] == "unreadable"
    assert view["receipts"] == []


def test_missions_route_over_http(tmp_path):
    server = HubServer(Hub(_home(tmp_path), "http://127.0.0.1:9", actor="desktop:tester"), 0)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
    thread.start()
    try:
        base = server.url.rstrip("/")
        all_items = requests.get(base + "/hub/api/missions", timeout=10)
        assert all_items.status_code == 200
        assert [item["task_id"] for item in all_items.json()["receipts"]] == ["task-a", "task-b", "task-c"]
        blocked = requests.get(base + "/hub/api/missions?status=BLOCKED", timeout=10)
        assert blocked.status_code == 200
        assert [item["task_id"] for item in blocked.json()["receipts"]] == ["task-b"]
    finally:
        server.shutdown()
        thread.join(timeout=10)
