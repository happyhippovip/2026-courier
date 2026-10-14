"""Kolibri: one flower per source, bird rests unless the evidence is live."""

import json
import subprocess
import threading
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from courier_core.events import Event, EventType
from courier_core.journal import Journal
from courier_hub.kolibri_data import (
    PAUSE, REST_TEXT, UNAVAILABLE, _display_path, build_snapshot, read_github, station_key,
)
from courier_hub.server import Hub, HubServer

REPO = Path(__file__).resolve().parents[2]
WALL = REPO / "scripts" / "windows_muse_wall" / "runtime" / "slots"
MUSE_LABEL = "muse wall"
OFFLINE = lambda _path: None  # no token and no fabricated GitHub body


def _render(snapshot: dict) -> tuple[str, int]:
    script = r"""
import { pathToFileURL } from "node:url";
const mod = await import(pathToFileURL(process.argv[1]).href);
const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const snapshot = JSON.parse(Buffer.concat(chunks).toString("utf8"));
const html = mod.renderKolibri(snapshot);
process.stdout.write(JSON.stringify({ html, poll: mod.POLL_MS, rest: mod.REST_TEXT }));
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(REPO / "courier_hub" / "static" / "kolibri_core.mjs")],
        input=json.dumps(snapshot).encode("utf-8"),
        capture_output=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    return payload["html"], payload["poll"]


def _hub(home: Path) -> Hub:
    return Hub(home, "http://127.0.0.1:9", actor="desktop:kolibri", timeout_s=0.2)


def _journal(home: Path, title: str, task_id: str = "kolibri-ledger") -> None:
    with Journal(home / "courier.db") as journal:
        journal.append(Event(type=EventType.TASK_CREATED, task_id=task_id, payload={
            "adapter": "synthetic",
            "params": {"title": title},
            "effect_class": "idempotent",
            "max_attempts": 3,
            "lease_ttl_s": 6,
        }))


def _git_repo(path: Path, subject: str, branch: str = "integration/v1") -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", branch], cwd=path, check=True, capture_output=True)
    (path / "README").write_text("note\n", encoding="utf-8")
    subprocess.run(["git", "add", "README"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=kolibri@example.com", "-c", "user.name=Kolibri", "commit", "-m", subject],
        cwd=path, check=True, capture_output=True,
    )


def _sample_fields(html: str, count: int = 5) -> list[str]:
    parts = html.split('<div class="field">')[1:]
    assert len(parts) >= count
    return parts[:count]


def test_station_order_is_numeric_and_stable():
    ids = ["MUSE-10", "MUSE-2", "MUSE-1", "desk", "alpha"]
    ordered = sorted(ids, key=station_key)
    assert ordered == ["MUSE-1", "MUSE-2", "MUSE-10", "alpha", "desk"]
    assert sorted(ids, key=station_key) == ordered
    assert station_key("MUSE-01")[1] == station_key("MUSE-1")[1] == 1


def test_view_renders_real_sources_with_traceable_values(tmp_path):
    home = tmp_path / "home"
    _journal(home, "Kolibri ledger row")
    # The checkout under test may have no local integration/v1 (CI checks out the PR head).
    repo = tmp_path / "repo"
    _git_repo(repo, "Fixture landing (#7)")
    snapshot = build_snapshot(
        _hub(home), root=repo, wall=WALL, wall_label=MUSE_LABEL,
        observed_at="2026-10-14T22:00:00Z", github_fetch=OFFLINE,
    )
    raw = json.dumps(snapshot)
    slot = json.loads((WALL / "MUSE-01" / "state.json").read_text(encoding="utf-8"))
    assert slot["owner_token"] not in raw
    assert slot["workdir"] not in raw
    assert "owner_token" not in raw
    assert "ghs_" not in raw

    muse = snapshot["muse_wall"]
    assert muse["available"] is True and muse["active"] is False
    assert muse["value"] == PAUSE
    assert [station["id"] for station in muse["stations"][:3]] == ["MUSE-01", "MUSE-02", "MUSE-03"]
    assert muse["stations"][-1]["id"] == "MUSE-64"
    first = muse["stations"][0]
    assert first["state"]["value"] == PAUSE
    assert first["heartbeat"] is False
    assert first["state"]["source"] == "MUSE-01/state.json"
    assert first["state"]["at"] != UNAVAILABLE
    assert first["process"]["value"] == "none"

    assert snapshot["ledger"]["available"] is True and snapshot["ledger"]["active"] is True
    assert any(item["title"] == "Kolibri ledger row" and item["at"] != UNAVAILABLE
               for item in snapshot["ledger"]["items"])
    assert snapshot["ledger_bridge"]["value"] == UNAVAILABLE
    assert snapshot["postfach_alt_an_neu"]["value"] == UNAVAILABLE
    assert snapshot["postfach_neu_an_alt"]["value"] == UNAVAILABLE
    assert snapshot["github_ci"]["value"] == UNAVAILABLE
    assert snapshot["draft_prs"]["value"] == UNAVAILABLE
    assert snapshot["merged_prs"]["available"] is True
    assert snapshot["merged_prs"]["source"] == "git log integration/v1"
    assert [row["pr"] for row in snapshot["merged_prs"]["rows"]] == [7]
    assert all(row["source"] == "git log integration/v1" and row["at"] != UNAVAILABLE
               for row in snapshot["merged_prs"]["rows"])
    times = [row["at"] for row in snapshot["merged_prs"]["rows"]]
    assert times == sorted(times)

    html, poll = _render(snapshot)
    assert 10000 <= poll <= 30000
    assert html.count("source ") >= 5 and html.count("timestamp ") >= 5
    for piece in _sample_fields(html):
        assert "source " in piece and "timestamp " in piece
    assert 'data-station="MUSE-01"' in html
    assert html.index('data-station="MUSE-09"') < html.index('data-station="MUSE-10"')
    assert "source MUSE-01/state.json" in html
    assert "scripts/windows_muse_wall" not in html
    assert "Users" not in html and "lol" not in raw and "/home/" not in raw
    assert f"timestamp {first['state']['at']}" in html
    assert ">READY<" not in html
    assert f">{PAUSE}<" in html
    assert 'data-bird="fly"' in html and 'data-target="ledger"' in html
    assert REST_TEXT not in html
    assert slot["owner_token"] not in html


def test_no_activity_bird_rests(tmp_path):
    home = tmp_path / "home"
    with Journal(home / "courier.db"):
        pass
    wall = tmp_path / "wall"
    slot = wall / "MUSE-01"
    slot.mkdir(parents=True)
    (slot / "state.json").write_text(json.dumps({
        "slot_id": "MUSE-01", "state": "READY", "process": None, "updated_at": 1_700_000_000,
    }), encoding="utf-8")
    (home / "ledger_bridge_state.json").write_text(json.dumps({"missions": {}}), encoding="utf-8")
    (home / "POSTFACH_ALT_AN_NEU").write_text("[]", encoding="utf-8")
    (home / "POSTFACH_NEU_AN_ALT.json").write_text("[]", encoding="utf-8")
    snapshot = build_snapshot(
        _hub(home), root=tmp_path / "no-repo", wall=wall, wall_label="wall",
        observed_at="2026-10-14T22:00:00Z", github_fetch=OFFLINE,
    )
    assert snapshot["muse_wall"]["value"] == PAUSE
    assert snapshot["muse_wall"]["stations"][0]["state"]["value"] == PAUSE
    assert snapshot["ledger"]["available"] is True and snapshot["ledger"]["active"] is False
    assert snapshot["ledger_bridge"]["available"] is True and snapshot["ledger_bridge"]["active"] is False
    assert snapshot["postfach_alt_an_neu"]["value"] == "0"
    assert snapshot["postfach_neu_an_alt"]["value"] == "0"
    assert snapshot["bird"]["state"] == "rest"
    assert snapshot["activity"] == REST_TEXT
    html, _poll = _render(snapshot)
    assert 'data-bird="rest"' in html
    assert 'data-state="rest"' in html
    assert f">{REST_TEXT}<" in html
    assert 'data-state="fly"' not in html
    assert ">READY<" not in html
    for flower in ("muse_wall", "ledger", "ledger_bridge", "postfach_alt_an_neu", "postfach_neu_an_alt"):
        assert f'data-flower="{flower}"' in html


def test_unreachable_source_is_unknown_without_an_invented_value(tmp_path):
    snapshot = build_snapshot(
        _hub(tmp_path / "empty-home"),
        root=tmp_path / "no-repo",
        wall=tmp_path / "no-wall",
        wall_label=MUSE_LABEL,
        observed_at="2026-10-14T22:00:00Z",
        github_fetch=OFFLINE,
    )
    for key in ("muse_wall", "ledger", "ledger_bridge", "postfach_alt_an_neu", "postfach_neu_an_alt",
                "github_ci", "draft_prs", "merged_prs"):
        assert snapshot[key]["available"] is False
        assert snapshot[key]["active"] is False
        assert snapshot[key]["value"] == UNAVAILABLE
    assert snapshot["muse_wall"]["stations"] == []
    assert snapshot["bird"]["state"] == "rest"
    html, _poll = _render(snapshot)
    assert html.count(UNAVAILABLE) >= 8
    assert "READY" not in html
    assert PAUSE not in html
    assert 'data-station=' not in html
    assert "source ledger_bridge_state.json" in html
    assert "source POSTFACH_ALT_AN_NEU" in html
    assert "source POSTFACH_NEU_AN_ALT" in html
    assert "source github statuses integration/v1" in html
    assert f">{REST_TEXT}<" in html


def test_github_payload_is_shown_and_a_failed_read_is_unknown():
    ci, drafts = read_github(REPO, "2026-10-14T22:00:00Z", fetch=OFFLINE)
    assert ci["value"] == UNAVAILABLE and drafts["value"] == UNAVAILABLE

    def fetch(path: str):
        if path.endswith("/status"):
            return {"state": "success", "sha": "abc", "statuses": [
                {"context": "ci", "state": "success", "updated_at": "2026-01-01T00:00:00Z"},
            ]}
        return [{"number": 15, "draft": True, "title": "Open draft", "updated_at": "2026-10-14T21:00:00Z"},
                {"number": 16, "draft": False, "title": "Not a draft", "updated_at": "2026-10-14T21:00:00Z"}]

    ci, drafts = read_github(REPO, "2026-10-14T22:00:00Z", fetch=fetch)
    assert ci["value"] == "success"
    assert ci["checks"][0]["context"] == "ci"
    assert ci["checks"][0]["at"] == "2026-01-01T00:00:00Z"
    assert ci["active"] is False
    assert [row["pr"] for row in drafts["rows"]] == [15]
    assert drafts["active"] is True
    assert drafts["rows"][0]["source"] == "github pulls integration/v1"


def test_fresh_heartbeat_is_not_pause(tmp_path):
    observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    wall = tmp_path / "wall" / "MUSE-02"
    wall.mkdir(parents=True)
    (wall / "state.json").write_text(json.dumps({
        "slot_id": "MUSE-02",
        "state": "READY",
        "process": {"pid": 1},
        "updated_at": datetime.now(timezone.utc).timestamp(),
    }), encoding="utf-8")
    snapshot = build_snapshot(
        _hub(tmp_path / "home"), root=tmp_path / "no-repo", wall=tmp_path / "wall",
        wall_label="wall", observed_at=observed, github_fetch=OFFLINE,
    )
    station = snapshot["muse_wall"]["stations"][0]
    assert station["heartbeat"] is True
    assert station["state"]["value"] == "READY"
    assert snapshot["muse_wall"]["active"] is True
    html, _poll = _render(snapshot)
    assert 'data-bird="fly"' in html
    assert 'data-target="muse_wall"' in html
    assert REST_TEXT not in html


def test_new_journal_entry_is_visible_on_the_next_poll(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    server = HubServer(_hub(home), 0)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/hub/api/kolibri", timeout=20) as response:
            before = json.loads(response.read().decode("utf-8"))
        assert before["ledger"]["value"] == UNAVAILABLE
        _journal(home, "Kolibri poll row", task_id="kolibri-poll")
        with urllib.request.urlopen(base + "/hub/api/kolibri", timeout=20) as response:
            after = json.loads(response.read().decode("utf-8"))
        titles = [item["title"] for item in after["ledger"]["items"]]
        assert "Kolibri poll row" in titles
        assert after["ledger"]["active"] is True
        assert all(item["source"] and item["at"] for item in after["ledger"]["items"])
        _html, poll = _render(after)
        assert poll <= 30000
    finally:
        server.shutdown()
        server.server_close()


def test_merged_ref_uses_origin_then_unknown(tmp_path):
    remote_only = tmp_path / "remote-only"
    _git_repo(remote_only, "Remote landing (#9)", branch="other")
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/integration/v1", "HEAD"],
        cwd=remote_only, check=True, capture_output=True,
    )
    missing_local = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", "refs/heads/integration/v1"],
        cwd=remote_only, check=False,
    )
    assert missing_local.returncode != 0
    seen = build_snapshot(
        _hub(tmp_path / "home-remote"), root=remote_only, wall=tmp_path / "no-wall",
        wall_label="wall", observed_at="2026-10-14T22:00:00Z", github_fetch=OFFLINE,
    )
    assert seen["merged_prs"]["available"] is True
    assert seen["merged_prs"]["source"] == "git log origin/integration/v1"
    assert [row["pr"] for row in seen["merged_prs"]["rows"]] == [9]
    assert seen["merged_prs"]["rows"][0]["source"] == "git log origin/integration/v1"

    neither = tmp_path / "neither"
    _git_repo(neither, "Unrelated", branch="other")
    absent = build_snapshot(
        _hub(tmp_path / "home-absent"), root=neither, wall=tmp_path / "no-wall-2",
        wall_label="wall", observed_at="2026-10-14T22:00:00Z", github_fetch=OFFLINE,
    )
    assert absent["merged_prs"]["available"] is False
    assert absent["merged_prs"]["value"] == UNAVAILABLE
    assert absent["merged_prs"]["source"] == "git log integration/v1"


def test_local_merge_subject_is_a_row_without_a_fixed_number(tmp_path):
    repo = tmp_path / "repo"
    _git_repo(repo, "Land the note (#4242)")
    snapshot = build_snapshot(
        _hub(tmp_path / "home"), root=repo, wall=tmp_path / "missing-wall", wall_label="wall",
        observed_at="2026-10-14T22:00:00Z", github_fetch=OFFLINE,
    )
    rows = snapshot["merged_prs"]["rows"]
    assert [row["pr"] for row in rows] == [4242]
    assert rows[0]["source"] == "git log integration/v1"
    assert rows[0]["at"] != UNAVAILABLE


def test_hub_route_serves_one_page(tmp_path):
    server = HubServer(_hub(tmp_path / "home"), 0)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/hub/api/kolibri", timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
        assert body["muse_wall"]["stations"][0]["state"]["value"] == PAUSE
        assert body["ledger"]["value"] == UNAVAILABLE
        for key in ("ledger_bridge", "postfach_alt_an_neu", "postfach_neu_an_alt", "github_ci", "draft_prs"):
            assert key in body
        raw = json.dumps(body)
        slot = json.loads((WALL / "MUSE-01" / "state.json").read_text(encoding="utf-8"))
        assert slot["owner_token"] not in raw
        assert "ghs_" not in raw
        assert "Users" not in raw and "lol" not in raw and "/home/" not in raw
        assert body["muse_wall"]["stations"][0]["state"]["source"] == "MUSE-01/state.json"
        assert ">READY<" not in raw
        with urllib.request.urlopen(base + "/kolibri.html", timeout=10) as response:
            assert response.status == 200
            page = response.read().decode("utf-8")
        assert page.count("<main") == 1 and "kolibri.js" in page
    finally:
        server.shutdown()
        server.server_close()


def _commit(path: Path, name: str, subject: str) -> None:
    (path / name).write_text(name + "\n", encoding="utf-8")
    subprocess.run(["git", "add", name], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=kolibri@example.com", "-c", "user.name=Kolibri", "commit", "-m", subject],
        cwd=path, check=True, capture_output=True,
    )


def _slot(wall: Path, slot_id: str, payload: dict) -> None:
    slot = wall / slot_id
    slot.mkdir(parents=True, exist_ok=True)
    (slot / "state.json").write_text(json.dumps(payload), encoding="utf-8")


def test_display_path_hides_home_user_and_internal_prefix(tmp_path):
    root = tmp_path / "repo"
    samples = {
        Path("/home/ubuntu/ledger_bridge_state.json"): "ledger_bridge_state.json",
        Path("/Users/lol/2026-workspace/ledger_bridge_state.json"): "ledger_bridge_state.json",
        Path("/home/dennis"): "source",
        Path("C:/Users/lol/2026-courier/scripts/windows_muse_wall/runtime/slots/MUSE-04/state.json"): "MUSE-04/state.json",
        root / "scripts" / "windows_muse_wall" / "runtime" / "slots" / "MUSE-01" / "state.json": "MUSE-01/state.json",
    }
    for path, expected in samples.items():
        shown = _display_path(path, root)
        assert shown == expected
        assert not shown.startswith("/") and "\\" not in shown
        assert "ubuntu" not in shown and "dennis" not in shown and "lol" not in shown
        assert "Users" not in shown and "scripts/" not in shown


def test_checked_in_ready_is_pause_even_when_the_stamp_is_fresh(tmp_path):
    observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    wall = tmp_path / "wall"
    _slot(wall, "MUSE-01", {
        "slot_id": "MUSE-01",
        "state": "READY",
        "process": None,
        "updated_at": datetime.now(timezone.utc).timestamp(),
        "workdir": "C:\\Users\\lol\\2026-workspace\\slots\\MUSE-01\\workdir",
    })
    snapshot = build_snapshot(
        _hub(tmp_path / "home"), root=tmp_path / "no-repo", wall=wall, wall_label="muse wall",
        observed_at=observed, github_fetch=OFFLINE,
    )
    station = snapshot["muse_wall"]["stations"][0]
    assert station["heartbeat"] is False
    assert station["state"]["value"] == PAUSE
    assert station["process"]["value"] == "none"
    html, _poll = _render(snapshot)
    assert ">READY<" not in html
    assert "lol" not in html and "Users" not in html


def test_process_timestamp_is_a_live_heartbeat_and_stale_ready_is_not(tmp_path):
    observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    now = datetime.now(timezone.utc).timestamp()
    wall = tmp_path / "wall"
    _slot(wall, "MUSE-02", {
        "slot_id": "MUSE-02",
        "state": "READY",
        "process": {"pid": 4, "create_time": now},
        "updated_at": 1_700_000_000,
    })
    _slot(wall, "MUSE-10", {
        "slot_id": "MUSE-10",
        "state": "READY",
        "process": {"pid": 9, "create_time": 1_700_000_000},
        "updated_at": 1_700_000_000,
    })
    (wall / "MUSE-03").mkdir(parents=True)
    (wall / "MUSE-03" / "state.json").write_text(json.dumps({
        "slot_id": "MUSE-03", "state": "READY", "process": None, "updated_at": 1_700_000_000,
    }), encoding="utf-8")
    (wall / "MUSE-03" / "heartbeat.json").write_text(json.dumps({
        "create_time": now,
    }), encoding="utf-8")
    snapshot = build_snapshot(
        _hub(tmp_path / "home"), root=tmp_path / "no-repo", wall=wall, wall_label="muse wall",
        observed_at=observed, github_fetch=OFFLINE,
    )
    by_id = {station["id"]: station for station in snapshot["muse_wall"]["stations"]}
    assert [station["id"] for station in snapshot["muse_wall"]["stations"]] == ["MUSE-02", "MUSE-03", "MUSE-10"]
    assert by_id["MUSE-02"]["heartbeat"] is True
    assert by_id["MUSE-02"]["state"]["value"] == UNAVAILABLE
    assert by_id["MUSE-10"]["heartbeat"] is False
    assert by_id["MUSE-10"]["state"]["value"] == PAUSE
    assert by_id["MUSE-03"]["heartbeat"] is True
    assert by_id["MUSE-03"]["state"]["value"] == UNAVAILABLE
    assert by_id["MUSE-03"]["state"]["source"] == "MUSE-03/heartbeat.json"
    html, _poll = _render(snapshot)
    assert ">READY<" not in html
    assert html.index('data-station="MUSE-03"') < html.index('data-station="MUSE-10"')


def test_ledger_bridge_reads_state_entries_and_journal(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "ledger_bridge_state.json").write_text(json.dumps({
        "missions": {
            "A": {
                "task_id": "task-a",
                "status": "POSTED",
                "reason": "WAITING",
                "updated_at": "2026-10-14T21:00:00Z",
            },
            "B": {"task_id": "task-b"},
        },
    }), encoding="utf-8")
    (home / "coordination_ledger.jsonl").write_text("\n".join([
        json.dumps({
            "event_id": "e1", "mission_id": "B", "status": "WORKING",
            "event_type": "STARTED", "created_at": "2026-10-14T20:00:00Z",
        }),
        json.dumps({
            "event_id": "e2", "mission_id": "C", "status": "DONE",
            "event_type": "FINAL", "created_at": "2026-10-14T21:30:00Z",
        }),
        "not json",
        json.dumps({"mission_id": "D", "status": "GUESS", "created_at": "2026-10-14T21:30:00Z"}),
    ]) + "\n", encoding="utf-8")
    snapshot = build_snapshot(
        _hub(home), root=tmp_path / "no-repo", wall=tmp_path / "no-wall", wall_label="muse wall",
        observed_at="2026-10-14T22:00:00Z", github_fetch=OFFLINE,
    )
    bridge = snapshot["ledger_bridge"]
    assert bridge["available"] is True
    assert bridge["source"] == "ledger_bridge_state.json"
    by_id = {row["id"]: row for row in bridge["missions"]}
    assert list(by_id) == ["A", "B", "C"]
    assert by_id["A"]["status"] == "POSTED"
    assert by_id["A"]["task_id"] == "task-a"
    assert by_id["A"]["reason"] == "WAITING"
    assert by_id["A"]["at"] == "2026-10-14T21:00:00Z"
    assert by_id["A"]["source"] == "ledger_bridge_state.json"
    assert by_id["B"]["status"] == "WORKING"
    assert by_id["B"]["task_id"] == "task-b"
    assert by_id["B"]["source"] == "ledger_bridge_state.json"
    assert by_id["B"]["status_source"] == "coordination_ledger.jsonl"
    assert by_id["B"]["status_at"] == "2026-10-14T20:00:00Z"
    assert by_id["B"]["event_type"] == "STARTED"
    assert by_id["C"]["status"] == "DONE"
    assert by_id["C"]["source"] == "coordination_ledger.jsonl"
    html, _poll = _render(snapshot)
    assert 'data-mission="A"' in html
    assert "source ledger_bridge_state.json" in html
    assert "source coordination_ledger.jsonl" in html
    assert "timestamp 2026-10-14T21:00:00Z" in html
    assert "GUESS" not in html


def test_ledger_journal_alone_is_the_bridge_and_a_missing_journal_stays_unknown(tmp_path):
    home = tmp_path / "journal-only"
    home.mkdir()
    (home / "coordination_ledger.jsonl").write_text(json.dumps({
        "event_id": "e1", "mission_id": "M", "status": "BLOCKED",
        "event_type": "BLOCKED", "created_at": "2026-10-01T00:00:00Z",
    }) + "\n", encoding="utf-8")
    seen = build_snapshot(
        _hub(home), root=tmp_path / "no-repo", wall=tmp_path / "no-wall", wall_label="muse wall",
        observed_at="2026-10-14T22:00:00Z", github_fetch=OFFLINE,
    )
    assert seen["ledger_bridge"]["available"] is True
    assert seen["ledger_bridge"]["source"] == "coordination_ledger.jsonl"
    assert seen["ledger_bridge"]["missions"][0]["status"] == "BLOCKED"
    assert seen["ledger_bridge"]["missions"][0]["at"] == "2026-10-01T00:00:00Z"
    absent = build_snapshot(
        _hub(tmp_path / "empty"), root=tmp_path / "no-repo-2", wall=tmp_path / "no-wall-2",
        wall_label="muse wall", observed_at="2026-10-14T22:00:00Z", github_fetch=OFFLINE,
    )
    assert absent["ledger_bridge"]["value"] == UNAVAILABLE
    assert absent["ledger_bridge"]["missions"] == []


def test_done_uses_the_ref_that_contains_the_merge_and_the_slot_number(tmp_path):
    repo = tmp_path / "repo"
    _git_repo(repo, "Base")
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    _commit(repo, "local.txt", "Ship MUSE-2 (#3)")
    subprocess.run(["git", "checkout", "-B", "other", base], cwd=repo, check=True, capture_output=True)
    _commit(repo, "origin.txt", "Merge pull request #5 from example/muse\n\nLand MUSE-10 on the wall")
    origin = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    subprocess.run(["git", "update-ref", "refs/remotes/origin/integration/v1", origin], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "integration/v1"], cwd=repo, check=True, capture_output=True)
    wall = tmp_path / "wall"
    for slot_id in ("MUSE-01", "MUSE-02", "MUSE-10"):
        _slot(wall, slot_id, {"slot_id": slot_id, "state": "READY", "process": None, "updated_at": 1})
    snapshot = build_snapshot(
        _hub(tmp_path / "home"), root=repo, wall=wall, wall_label="muse wall",
        observed_at="2026-10-14T22:00:00Z", github_fetch=OFFLINE,
    )
    assert "git log integration/v1" in snapshot["merged_prs"]["source"]
    assert "git log origin/integration/v1" in snapshot["merged_prs"]["source"]
    assert sorted(row["pr"] for row in snapshot["merged_prs"]["rows"]) == [3, 5]
    by_id = {station["id"]: station["done"] for station in snapshot["muse_wall"]["stations"]}
    assert [station["id"] for station in snapshot["muse_wall"]["stations"]] == ["MUSE-01", "MUSE-02", "MUSE-10"]
    assert by_id["MUSE-02"]["value"] == "DONE" and by_id["MUSE-02"]["pr"] == 3
    assert by_id["MUSE-10"]["value"] == "DONE" and by_id["MUSE-10"]["pr"] == 5
    assert by_id["MUSE-01"]["value"] == "not done"
    assert by_id["MUSE-10"]["source"].startswith("git log origin/integration/v1")


def test_stale_local_integration_does_not_hide_origin_merges(tmp_path):
    repo = tmp_path / "repo"
    _git_repo(repo, "Old landing (#1)")
    old = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    _commit(repo, "new.txt", "Finish MUSE-04 (#8)")
    new = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    subprocess.run(["git", "checkout", "--detach"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "update-ref", "refs/heads/integration/v1", old], cwd=repo, check=True)
    subprocess.run(["git", "update-ref", "refs/remotes/origin/integration/v1", new], cwd=repo, check=True)
    wall = tmp_path / "wall"
    _slot(wall, "MUSE-04", {"slot_id": "MUSE-04", "state": "READY", "process": None, "updated_at": 1})
    snapshot = build_snapshot(
        _hub(tmp_path / "home"), root=repo, wall=wall, wall_label="muse wall",
        observed_at="2026-10-14T22:00:00Z", github_fetch=OFFLINE,
    )
    assert snapshot["merged_prs"]["source"] == "git log origin/integration/v1"
    assert [row["pr"] for row in snapshot["merged_prs"]["rows"]] == [1, 8]
    assert snapshot["muse_wall"]["stations"][0]["done"]["value"] == "DONE"
    assert snapshot["muse_wall"]["stations"][0]["done"]["pr"] == 8
