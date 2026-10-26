"""Kolibri: one flower per source, bird rests unless the evidence is live."""

import json
import subprocess
import threading
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from courier_core.events import Event, EventType
from courier_core.journal import Journal
from courier_hub.kolibri_data import PAUSE, REST_TEXT, UNAVAILABLE, build_snapshot, read_github, read_ledger_bridge, read_muse_wall, read_postfach, station_key
from courier_hub.server import Hub, HubServer

REPO = Path(__file__).resolve().parents[2]
WALL = REPO / "scripts" / "windows_muse_wall" / "runtime" / "slots"
MUSE_LABEL = "scripts/windows_muse_wall/runtime/slots"
OFFLINE = lambda _path: None  # no token and no fabricated GitHub body


def test_read_muse_wall_refuses_a_symlink(tmp_path):
    outside = tmp_path / "outside"
    (outside / "01").mkdir(parents=True)
    secret = {"slot_id": "SECRET", "state": "SECRET", "process": 1, "updated_at": datetime.now(timezone.utc).timestamp()}
    (outside / "01" / "state.json").write_text(json.dumps(secret), encoding="utf-8")
    root = tmp_path / "repo"
    root.mkdir()
    linked = tmp_path / "linked-wall"
    linked.symlink_to(outside)
    merged = {"available": False}
    block = read_muse_wall(root, linked, "wall", "2026-10-26T04:47:00Z", merged)
    assert block["available"] is False
    assert block["stations"] == []
    assert "SECRET" not in json.dumps(block)

    wall = tmp_path / "wall"
    (wall / "01").mkdir(parents=True)
    (wall / "01" / "state.json").symlink_to(outside / "01" / "state.json")
    skipped = read_muse_wall(root, wall, "wall", "2026-10-26T04:47:00Z", merged)
    assert skipped["stations"] == []
    assert "SECRET" not in json.dumps(skipped)

    now = datetime.now(timezone.utc)
    (wall / "01" / "state.json").unlink()
    (wall / "01" / "state.json").write_text(
        json.dumps({"slot_id": "LIVE-01", "state": "RUNNING", "process": 1, "updated_at": now.timestamp()}),
        encoding="utf-8",
    )
    live = read_muse_wall(root, wall, "wall", now.strftime("%Y-%m-%dT%H:%M:%SZ"), merged)
    assert live["stations"][0]["id"] == "LIVE-01"
    assert live["stations"][0]["state"]["value"] == "RUNNING"


def test_read_postfach_refuses_a_symlink(tmp_path, monkeypatch):
    monkeypatch.delenv("COURIER_POSTFACH_DIR", raising=False)
    outside = tmp_path / "secret.json"
    outside.write_text('[{"secret":"SECRET"}]', encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    root = tmp_path / "repo"
    root.mkdir()
    (home / "POSTFACH_ALT_AN_NEU").symlink_to(outside)
    block = read_postfach("postfach_alt_an_neu", home, root, "2026-10-26T04:43:00Z")
    assert block["entries"] is None
    assert "SECRET" not in json.dumps(block)
    assert "SECRET" in outside.read_text(encoding="utf-8")

    linked = tmp_path / "linked-home"
    linked.symlink_to(home)
    (home / "POSTFACH_ALT_AN_NEU").unlink()
    (home / "POSTFACH_ALT_AN_NEU").write_text('[{"secret":"SECRET"}]', encoding="utf-8")
    through = read_postfach("postfach_alt_an_neu", linked, root, "2026-10-26T04:43:00Z")
    assert through["entries"] is None
    assert "SECRET" not in json.dumps(through)

    live = read_postfach("postfach_alt_an_neu", home, root, "2026-10-26T04:43:00Z")
    assert live["entries"] == 1
    assert live["available"] is True


def test_read_ledger_bridge_refuses_a_symlink(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"missions": {"A": {"status": "SECRET"}}}), encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    (home / "ledger_bridge_state.json").symlink_to(outside)
    block = read_ledger_bridge(home, tmp_path, "2026-10-26T04:40:00Z")
    assert block["missions"] == []
    assert "SECRET" not in json.dumps(block)
    assert "SECRET" in outside.read_text(encoding="utf-8")

    (home / "ledger_bridge_state.json").unlink()
    (home / "ledger_bridge_state.json").write_text(
        json.dumps({"missions": {"A": {"status": "WORKING", "updated_at": "2026-10-26T04:40:00Z"}}}),
        encoding="utf-8",
    )
    live = read_ledger_bridge(home, tmp_path, "2026-10-26T04:40:00Z")
    assert live["missions"][0]["id"] == "A"
    assert live["missions"][0]["status"] == "WORKING"


def test_read_ledger_bridge_refuses_a_file_two_levels_under_a_symlink(tmp_path):
    outside = tmp_path / "outside"
    mid = outside / "mid"
    mid.mkdir(parents=True)
    secret = mid / "ledger_bridge_state.json"
    secret.write_text(json.dumps({"missions": {"A": {"status": "SECRET"}}}), encoding="utf-8")
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)
    block = read_ledger_bridge(link / "mid", tmp_path, "2026-10-26T04:40:00Z")
    assert block["missions"] == []
    assert "SECRET" not in json.dumps(block)
    assert "SECRET" in secret.read_text(encoding="utf-8")

    real = tmp_path / "real"
    real.mkdir()
    (real / "ledger_bridge_state.json").write_text(
        json.dumps({"missions": {"A": {"status": "WORKING", "updated_at": "2026-10-26T04:40:00Z"}}}),
        encoding="utf-8",
    )
    live = read_ledger_bridge(real, tmp_path, "2026-10-26T04:40:00Z")
    assert live["missions"][0]["id"] == "A"
    assert live["missions"][0]["status"] == "WORKING"


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
    hub = Hub(home, "http://127.0.0.1:9", actor="desktop:kolibri", timeout_s=0.2)
    hub.github_fetch = OFFLINE
    return hub


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
    ids = ["MUSE-10", "MUSE-2", "MUSE-1", "desk"]
    ordered = sorted(ids, key=station_key)
    assert ordered == ["MUSE-1", "MUSE-2", "MUSE-10", "desk"]
    assert sorted(ids, key=station_key) == ordered


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
    assert first["state"]["source"] == f"{MUSE_LABEL}/MUSE-01/state.json"
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
    assert f"source {MUSE_LABEL}/MUSE-01/state.json" in html
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
        with urllib.request.urlopen(base + "/kolibri.html", timeout=10) as response:
            assert response.status == 200
            page = response.read().decode("utf-8")
        assert page.count("<main") == 1 and "kolibri.js" in page
        with urllib.request.urlopen(base + "/kolibri", timeout=10) as response:
            assert response.status == 200
            alias_page = response.read().decode("utf-8")
        assert alias_page == page
    finally:
        server.shutdown()
        server.server_close()


def test_kolibri_workkey_lease_blocker_and_resource_pause_visibility(tmp_path):
    observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    now_ts = datetime.now(timezone.utc).timestamp()
    wall = tmp_path / "wall"
    slot_live = wall / "MUSE-01"
    slot_paused = wall / "MUSE-02"
    slot_live.mkdir(parents=True)
    slot_paused.mkdir(parents=True)
    (slot_live / "state.json").write_text(json.dumps({
        "slot_id": "MUSE-01",
        "state": "RUNNING",
        "process": {"pid": 42},
        "updated_at": now_ts,
        "workkey": "K-000019",
        "owner": "L4-verifier",
        "lease": "LEASE_ACTIVE",
        "owner_token": "secret-token-never-show",
    }), encoding="utf-8")
    (slot_paused / "state.json").write_text(json.dumps({
        "slot_id": "MUSE-02",
        "state": "READY",
        "process": None,
        "updated_at": 1_700_000_000,
        "workkey": "STALE-WORKKEY-HIDDEN",
        "blocker": "WAITING_AUTHORITY",
        "resource_pause": True,
    }), encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir(parents=True)
    (home / "ledger_bridge_state.json").write_text(json.dumps({
        "missions": {
            "M-KOLIBRI-1": {
                "status": "IN_PROGRESS",
                "workkey": "K-000003",
                "owner": "L2-controller",
                "lease": "LEASE_VALID",
                "resource_pause": "RESPECT",
                "updated_at": observed,
            }
        }
    }), encoding="utf-8")
    snapshot = build_snapshot(
        _hub(home), root=tmp_path / "no-repo", wall=wall, wall_label="wall",
        observed_at=observed, github_fetch=OFFLINE,
    )
    s1, s2 = snapshot["muse_wall"]["stations"]
    assert s1["workkey"]["value"] == "K-000019"
    assert s1["owner"]["value"] == "L4-verifier"
    assert s1["lease"]["value"] == "LEASE_ACTIVE"
    assert "workkey" not in s2  # stale slot must not claim active workkey
    assert s2["blocker"]["value"] == "WAITING_AUTHORITY"
    assert s2["resource_pause"]["value"] == "RESOURCE_PAUSE"
    html, _ = _render(snapshot)
    assert "K-000019" in html and "L4-verifier" in html and "LEASE_ACTIVE" in html
    assert "STALE-WORKKEY-HIDDEN" not in html
    assert "WAITING_AUTHORITY" in html and "RESOURCE_PAUSE" in html
    assert "K-000003" in html and "LEASE_VALID" in html
    assert "secret-token-never-show" not in html


def test_kolibri_static_script_lifecycle_guards() -> None:
    kolibri_js = (REPO / "courier_hub" / "static" / "kolibri.js").read_text(encoding="utf-8")
    kolibri_html = (REPO / "courier_hub" / "static" / "kolibri.html").read_text(encoding="utf-8")
    assert "document.hidden" in kolibri_js
    assert "document.addEventListener(\"visibilitychange\"" in kolibri_js
    assert "window.addEventListener(\"focus\"" in kolibri_js
    assert "window.addEventListener(\"online\"" in kolibri_js
    assert "clearTimeout(timer);" in kolibri_js
    assert 'document.querySelector("#refresh")?.addEventListener("click"' in kolibri_js
    assert 'event.key === "r"' in kolibri_js
    assert '<button type="button" id="refresh"' in kolibri_html
    assert '<a class="skip" href="#view">Skip to view</a>' in kolibri_html
    assert '<main id="view" tabindex="-1">' in kolibri_html


def test_kolibri_flow_signal_translation() -> None:
    script = r"""
import { pathToFileURL } from "node:url";
const flow = await import(pathToFileURL(process.argv[1]).href);
const results = {
  running: flow.translateSignal({ state: { value: "RUNNING" }, id: "task-1" }),
  transferred: flow.translateSignal({ status: "TRANSFERRED", task_id: "task-2" }),
  claimed: flow.translateSignal({ status: "CLAIMED", id: "task-3" }),
  verifying: flow.translateSignal({ state: { value: "VERIFYING" }, id: "task-4" }),
  verified: flow.translateSignal({ verified: true, state: { value: "DONE" }, id: "task-5" }),
  blocked: flow.translateSignal({ blocker: { value: "WAITING_AUTHORITY" }, id: "task-6" }),
  failed: flow.translateSignal({ state: { value: "FAILED" }, id: "task-7" }),
  warn: flow.translateSignal({ status: "WARN", id: "task-8" }),
  router: flow.translateSignal({ status: "ROUTER", id: "task-9" }),
  infra: flow.translateSignal({ status: "INFRA", id: "task-10" }),
  unknown: flow.translateSignal({}),
};
process.stdout.write(JSON.stringify(results));
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(REPO / "courier_hub" / "static" / "kolibri_flow.mjs")],
        capture_output=True,
        check=True,
    )
    res = json.loads(proc.stdout)
    assert res["running"]["state"] == "RUNNING" and res["running"]["color"] == "#a855f7"
    assert res["transferred"]["state"] == "TRANSFERRED" and res["transferred"]["color"] == "#06b6d4"
    assert res["claimed"]["state"] == "CLAIMED" and res["claimed"]["color"] == "#14b8a6"
    assert res["verifying"]["state"] == "VERIFYING" and res["verifying"]["color"] == "#d8b46a"
    assert res["verified"]["state"] == "VERIFIED" and res["verified"]["color"] == "#10b981" and res["verified"]["verified"] is True
    assert res["blocked"]["state"] == "BLOCKED" and res["blocked"]["color"] == "#ef4444"
    assert res["failed"]["state"] == "FAILED" and res["failed"]["color"] == "#ef4444"
    assert res["warn"]["state"] == "WARN" and res["warn"]["color"] == "#f59e0b"
    assert res["router"]["state"] == "ROUTER" and res["router"]["color"] == "#ec4899"
    assert res["infra"]["state"] == "INFRA" and res["infra"]["color"] == "#3b82f6"
    assert res["unknown"]["state"] == "UNKNOWN" and res["unknown"]["color"] == "#6b7280"

