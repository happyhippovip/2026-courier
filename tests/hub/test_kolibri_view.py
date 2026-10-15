"""Kolibri: one flower per source, bird rests unless the evidence is live."""

import json
import re
import subprocess
import threading
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from courier_core.events import Event, EventType
from courier_core.journal import Journal
from courier_hub.kolibri_data import (
    PAUSE, REST_TEXT, STALE, UNAVAILABLE, _parse_merges, build_snapshot, read_github, station_key,
)
from courier_hub.server import Hub, HubServer

REPO = Path(__file__).resolve().parents[2]
WALL = REPO / "scripts" / "windows_muse_wall" / "runtime" / "slots"
MUSE_LABEL = "scripts/windows_muse_wall/runtime/slots"
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


def _snapshot(home: Path, root: Path, wall: Path, observed: str, label: str = "wall") -> dict:
    return build_snapshot(
        _hub(home), root=root, wall=wall, wall_label=label, observed_at=observed, github_fetch=OFFLINE,
    )


def _beat(age: int, **over) -> tuple[str, dict]:
    observed = datetime(2026, 10, 14, 22, 0, tzinfo=timezone.utc)
    stamp = (observed - timedelta(seconds=age)).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = {"schema": "courier.wall.heartbeat/v1", "host": "CAMERA-HOST-NAME", "fenster_id": "W03",
            "letzter_heartbeat": stamp, "status": "laeuft", "quelle": "runner"}
    body.update(over)
    return observed.strftime("%Y-%m-%dT%H:%M:%SZ"), body


def _wall_beat(directory: Path, body: dict, name: str = "win-W03.json") -> Path:
    wall = directory / "wall"
    (wall / "heartbeat").mkdir(parents=True)
    (wall / "heartbeat" / name).write_text(json.dumps(body), encoding="utf-8")
    return wall


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
    subprocess.run(["git", "update-ref", "refs/remotes/origin/integration/v1", "HEAD"], cwd=repo, check=True, capture_output=True)
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
    assert muse["value"] == UNAVAILABLE
    assert [station["id"] for station in muse["stations"][:3]] == ["MUSE-01", "MUSE-02", "MUSE-03"]
    assert muse["stations"][-1]["id"] == "MUSE-64"
    first = muse["stations"][0]
    assert first["state"]["value"] == UNAVAILABLE
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
    assert snapshot["merged_prs"]["source"] == "git log origin/integration/v1"
    assert [row["pr"] for row in snapshot["merged_prs"]["rows"]] == [7]
    assert all(row["source"] == "git log origin/integration/v1" and row["at"] != UNAVAILABLE
               for row in snapshot["merged_prs"]["rows"])
    times = [row["at"] for row in snapshot["merged_prs"]["rows"]]
    assert times == sorted(times, reverse=True)
    station_times = [station["state"]["at"] for station in muse["stations"]]
    assert station_times == sorted(station_times, reverse=True)

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
    assert f">{PAUSE}<" not in html
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
    assert snapshot["muse_wall"]["value"] == UNAVAILABLE
    assert snapshot["muse_wall"]["stations"][0]["state"]["value"] == UNAVAILABLE
    assert snapshot["ledger_bridge"]["value"] == REST_TEXT
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


def test_k1_slot_process_is_not_a_heartbeat(tmp_path):
    observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    wall = tmp_path / "wall" / "MUSE-02"
    wall.mkdir(parents=True)
    (wall / "state.json").write_text(json.dumps({
        "slot_id": "MUSE-02",
        "state": "READY",
        "process": {"pid": 1},
        "updated_at": datetime.now(timezone.utc).timestamp(),
    }), encoding="utf-8")
    snapshot = _snapshot(tmp_path / "home", tmp_path / "no-repo", tmp_path / "wall", observed)
    station = snapshot["muse_wall"]["stations"][0]
    assert station["heartbeat"] is False
    assert station["state"]["value"] == UNAVAILABLE
    assert snapshot["muse_wall"]["value"] == UNAVAILABLE
    assert snapshot["muse_wall"]["active"] is False
    html, _poll = _render(snapshot)
    assert ">READY<" not in html
    assert 'data-bird="rest"' in html


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
    subprocess.run(["git", "update-ref", "refs/remotes/origin/integration/v1", "HEAD"], cwd=repo, check=True, capture_output=True)
    snapshot = build_snapshot(
        _hub(tmp_path / "home"), root=repo, wall=tmp_path / "missing-wall", wall_label="wall",
        observed_at="2026-10-14T22:00:00Z", github_fetch=OFFLINE,
    )
    rows = snapshot["merged_prs"]["rows"]
    assert [row["pr"] for row in rows] == [4242]
    assert rows[0]["source"] == "git log origin/integration/v1"
    assert rows[0]["at"] != UNAVAILABLE


def test_hub_route_serves_one_page(tmp_path):
    server = HubServer(_hub(tmp_path / "home"), 0)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(base + "/hub/api/kolibri", timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
        assert body["muse_wall"]["stations"][0]["state"]["value"] == UNAVAILABLE
        assert all(station["state"]["value"] != "READY" for station in body["muse_wall"]["stations"])
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
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("age,value,live", [
    (29, "READY", True), (30, "READY", True), (31, STALE, False), (89, STALE, False), (90, STALE, False),
    (91, PAUSE, False), (299, PAUSE, False), (300, PAUSE, False), (301, UNAVAILABLE, False),
])
def test_k1_heartbeat_age_bands(tmp_path, age, value, live):
    observed, body = _beat(age)
    snapshot = _snapshot(tmp_path / "home", tmp_path / "no-repo", _wall_beat(tmp_path, body), observed)
    station = snapshot["muse_wall"]["stations"][0]
    assert (station["id"], station["state"]["value"], station["heartbeat"]) == ("W03", value, live)
    assert (snapshot["muse_wall"]["value"], snapshot["muse_wall"]["active"]) == (value, live)
    raw, (html, _poll) = json.dumps(snapshot), _render(snapshot)
    assert "CAMERA-HOST-NAME" not in raw and "CAMERA-HOST-NAME" not in html
    assert (">READY<" in html) is live


def test_k1_rejects_invalid_heartbeats(tmp_path):
    observed, beispiel = _beat(1, quelle="BEI" "SPIEL")
    dropped = _snapshot(tmp_path / "ha", tmp_path / "na", _wall_beat(tmp_path / "a", beispiel), observed)
    html, _poll = _render(dropped)
    assert dropped["muse_wall"]["stations"] == [] and dropped["muse_wall"]["value"] == UNAVAILABLE
    assert "BEISPIEL" not in html and ">READY<" not in html
    for index, ((_, body), window) in enumerate(((_beat(1, schema="other.schema"), None), (_beat(-6), "W03"))):
        snap = _snapshot(tmp_path / f"h{index}", tmp_path / f"n{index}", _wall_beat(tmp_path / f"c{index}", body), observed)
        station = snap["muse_wall"]["stations"][0]
        assert station["state"]["value"] == UNAVAILABLE and snap["muse_wall"]["active"] is False
        assert window is None or station["id"] == window
    wall = tmp_path / "d" / "wall"
    (wall / "heartbeat").mkdir(parents=True)
    (wall / "heartbeat" / "win-W03.json").write_bytes(b"\xff")
    unreadable = _snapshot(tmp_path / "hd", tmp_path / "nd", wall, observed)
    assert unreadable["muse_wall"]["stations"][0]["state"]["value"] == UNAVAILABLE


def test_k3_sort_newest_first_ties_by_id(tmp_path):
    observed = "2026-10-14T22:00:00Z"
    wall = tmp_path / "wall"
    (wall / "heartbeat").mkdir(parents=True)
    for name, window, stamp in (("a.json", "W03", "2026-10-14T21:00:00Z"), ("b.json", "W01", "2026-10-14T21:00:00Z"), ("c.json", "W02", "2026-10-14T21:30:00Z")):
        _seen, body = _beat(0, fenster_id=window, letzter_heartbeat=stamp)
        (wall / "heartbeat" / name).write_text(json.dumps(body), encoding="utf-8")
    snapshot = _snapshot(tmp_path / "home", tmp_path / "no-repo", wall, observed)
    assert [station["id"] for station in snapshot["muse_wall"]["stations"]] == ["W02", "W01", "W03"]
    html, _poll = _render(snapshot)
    assert html.index('data-station="W02"') < html.index('data-station="W01"') < html.index('data-station="W03"')
    rows = _parse_merges("\n".join([
        "aaa\x1f2026-10-14T21:00:00Z\x1fLand older (#3)",
        "bbb\x1f2026-10-14T21:00:00Z\x1fLand tie (#9)",
        "ccc\x1f2026-10-14T21:30:00Z\x1fLand new (#1)",
    ]), "git log integration/v1")
    assert [row["pr"] for row in rows] == [1, 3, 9]


def test_k5_product_code_has_no_stand_in_words():
    pattern = re.compile(r"mock|dummy|random|fake|demo|Math\.random", re.I)
    paths = [REPO / "courier_hub" / "kolibri_data.py", *sorted((REPO / "courier_hub" / "static").glob("kolibri*"))]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert pattern.search(text) is None
        if path.name == "kolibri_data.py":
            assert text.count("BEISPIEL") == 1
        else:
            assert "BEISPIEL" not in text


@pytest.mark.parametrize("status,value,live", [
    ("startet", "READY", True), ("pausiert", PAUSE, False), ("leerlauf", "leerlauf", False),
    ("beendet", "beendet", False), ("fehler", "FEHLER", False),
])
def test_k1_fresh_status_is_visible(tmp_path, status, value, live):
    observed, body = _beat(1, status=status)
    snapshot = _snapshot(tmp_path / "home", tmp_path / "no-repo", _wall_beat(tmp_path, body), observed)
    station = snapshot["muse_wall"]["stations"][0]
    assert (station["state"]["value"], station["heartbeat"], snapshot["muse_wall"]["value"]) == (value, live, value)
    assert snapshot["muse_wall"]["active"] is live


def test_k8_poll_interval_stays_within_30_seconds():
    _html, poll = _render({"observed_at": "2026-10-14T22:00:00Z"})
    assert 0 < poll <= 30000
