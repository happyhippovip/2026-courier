"""Kolibri reads the repo's Muse-Wall files, the ledger journal, and merged PRs."""

import json
import subprocess
from pathlib import Path

from courier_core.events import Event, EventType
from courier_core.journal import Journal
from courier_hub.kolibri_data import UNAVAILABLE, build_snapshot, station_key
from courier_hub.server import Hub, HubServer

REPO = Path(__file__).resolve().parents[2]
WALL = REPO / "scripts" / "windows_muse_wall" / "runtime" / "slots"
MUSE_LABEL = "scripts/windows_muse_wall/runtime/slots"


def _render(snapshot: dict) -> tuple[str, int]:
    script = r"""
import { pathToFileURL } from "node:url";
const mod = await import(pathToFileURL(process.argv[1]).href);
const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const snapshot = JSON.parse(Buffer.concat(chunks).toString("utf8"));
process.stdout.write(JSON.stringify({
  html: mod.renderKolibri(snapshot),
  poll: mod.POLL_MS,
  unavailable: mod.UNAVAILABLE,
}));
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


def _journal(home: Path, title: str) -> None:
    with Journal(home / "courier.db") as journal:
        journal.append(Event(type=EventType.TASK_CREATED, task_id="kolibri-ledger", payload={
            "adapter": "synthetic",
            "params": {"title": title},
            "effect_class": "idempotent",
            "max_attempts": 3,
            "lease_ttl_s": 6,
        }))


def test_station_order_is_numeric_and_stable():
    ids = ["MUSE-10", "MUSE-2", "MUSE-1", "desk"]
    ordered = sorted(ids, key=station_key)
    assert ordered == ["MUSE-1", "MUSE-2", "MUSE-10", "desk"]
    assert sorted(ids, key=station_key) == ordered


def test_view_renders_real_sources_and_names_each_one(tmp_path):
    home = tmp_path / "home"
    _journal(home, "Kolibri ledger row")
    snapshot = build_snapshot(
        _hub(home), root=REPO, wall=WALL, wall_label=MUSE_LABEL, observed_at="2026-10-14T22:00:00Z",
    )
    raw = json.dumps(snapshot)
    slot = json.loads((WALL / "MUSE-01" / "state.json").read_text(encoding="utf-8"))
    assert slot["owner_token"] not in raw
    assert slot["workdir"] not in raw
    assert "owner_token" not in raw

    muse = snapshot["muse_wall"]
    assert muse["available"] is True
    assert [station["id"] for station in muse["stations"][:3]] == ["MUSE-01", "MUSE-02", "MUSE-03"]
    assert muse["stations"][-1]["id"] == "MUSE-64"
    assert len(muse["stations"]) == 64
    first = muse["stations"][0]
    assert first["state"]["value"] == "READY"
    assert first["state"]["source"] == f"{MUSE_LABEL}/MUSE-01/state.json"
    assert first["state"]["at"] != UNAVAILABLE
    assert first["process"]["value"] == "none"
    assert first["done"]["source"] == "git log integration/v1"
    assert first["done"]["value"] in {"DONE", "not done"}

    merged = {row["pr"]: row for row in snapshot["merged_prs"]["rows"]}
    assert snapshot["merged_prs"]["available"] is True
    assert 630 in merged
    assert "list-cleaner" in merged[630]["subject"]
    assert merged[630]["source"] == "git log integration/v1"
    assert merged[630]["at"] != UNAVAILABLE
    times = [row["at"] for row in snapshot["merged_prs"]["rows"]]
    assert times == sorted(times)

    ledger_items = snapshot["ledger"]["items"]
    assert snapshot["ledger"]["available"] is True
    assert snapshot["ledger"]["source"] == "courier journal (courier.db)"
    assert any(item["title"] == "Kolibri ledger row" and item["at"] != UNAVAILABLE for item in ledger_items)

    html, poll = _render(snapshot)
    assert 10000 <= poll <= 30000
    assert 'data-station="MUSE-01"' in html
    assert html.index('data-station="MUSE-09"') < html.index('data-station="MUSE-10"')
    assert f"source {MUSE_LABEL}/MUSE-01/state.json" in html
    assert f"timestamp {first['state']['at']}" in html
    assert "Kolibri ledger row" in html
    assert "source courier journal (courier.db)" in html
    assert "source git log integration/v1" in html
    assert "#630" in html
    assert slot["owner_token"] not in html
    assert slot["workdir"] not in html


def test_missing_source_renders_unavailable_text(tmp_path):
    snapshot = build_snapshot(
        _hub(tmp_path / "empty-home"),
        root=tmp_path / "no-repo",
        wall=tmp_path / "no-wall",
        wall_label=MUSE_LABEL,
        observed_at="2026-10-14T22:00:00Z",
    )
    assert snapshot["muse_wall"]["available"] is False
    assert snapshot["muse_wall"]["value"] == UNAVAILABLE
    assert snapshot["muse_wall"]["stations"] == []
    assert snapshot["ledger"]["available"] is False
    assert snapshot["ledger"]["value"] == UNAVAILABLE
    assert snapshot["merged_prs"]["available"] is False
    assert snapshot["merged_prs"]["value"] == UNAVAILABLE

    html, _poll = _render(snapshot)
    assert html.count(UNAVAILABLE) >= 3
    assert 'id="muse-wall" data-available="no"' in html
    assert 'id="ledger" data-available="no"' in html
    assert 'id="merged" data-available="no"' in html
    assert "data-station=" not in html
    assert f"source {MUSE_LABEL}" in html
    assert "source courier journal (courier.db)" in html
    assert "source git log integration/v1" in html


def test_hub_route_serves_the_same_snapshot(tmp_path):
    server = HubServer(_hub(tmp_path / "home"), 0)
    thread_started = __import__("threading").Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
    thread_started.start()
    try:
        import urllib.request
        url = f"http://127.0.0.1:{server.server_address[1]}/hub/api/kolibri"
        with urllib.request.urlopen(url, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
        assert body["muse_wall"]["available"] is True
        assert body["muse_wall"]["stations"][0]["id"] == "MUSE-01"
        assert body["ledger"]["value"] == UNAVAILABLE
        page_url = f"http://127.0.0.1:{server.server_address[1]}/kolibri.html"
        with urllib.request.urlopen(page_url, timeout=10) as response:
            assert response.status == 200
            page = response.read().decode("utf-8")
        assert "kolibri.js" in page and UNAVAILABLE in page
        assert page.count("<main") == 1
        raw = json.dumps(body)
        slot = json.loads((WALL / "MUSE-01" / "state.json").read_text(encoding="utf-8"))
        assert slot["owner_token"] not in raw
    finally:
        server.shutdown()
        server.server_close()
