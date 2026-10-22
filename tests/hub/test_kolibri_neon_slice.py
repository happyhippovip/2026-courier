"""Kolibri Neon Signal Lab slice (V17): lane, LIVE/DEMO split, perf guards.

Vertical render tests only — no backend, no polling, no invented evidence.
"""

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = str(REPO / "courier_hub" / "static" / "kolibri_core.mjs")
PARTICLES = REPO / "courier_hub" / "static" / "kolibri_particles.mjs"
CSS = (REPO / "courier_hub" / "static" / "kolibri.css").read_text(encoding="utf-8")
JS = (REPO / "courier_hub" / "static" / "kolibri.js").read_text(encoding="utf-8")
HTML = (REPO / "courier_hub" / "static" / "kolibri.html").read_text(encoding="utf-8")

SCRIPT = r"""
import { pathToFileURL } from "node:url";
const core = await import(pathToFileURL(process.argv[1]).href);
const mode = process.argv[2];
const demo = core.demoSnapshot();
const out = { demoDeterministic: null };
if (mode === "demo-slice") {
  const a = core.renderKolibri(demo, { mode: "demo" });
  const b = core.renderKolibri(core.demoSnapshot(), { mode: "demo" });
  out.demoDeterministic = a === b;
  out.demoHtml = a;
} else if (mode === "live-slice") {
  const live = JSON.parse(JSON.stringify(demo));
  live.muse_wall.stations[0].state.value = "RUNNING";
  live.muse_wall.stations[1].blocker = { value: "WAITING_AUTHORITY", source: "demo-fixture", at: "2026-10-18T00:00:00Z" };
  live.muse_wall.stations[2].verified = true;
  live.muse_wall.stations[2].event_id = "journal:12:RESULT_ACCEPTED";
  live.muse_wall.stations[0].done = { value: "DONE", source: "demo-fixture", at: "2026-10-18T00:00:00Z" };
  out.liveHtml = core.renderKolibri(live, { mode: "live" });
  out.detailHtml = core.renderDetail(live, "DEMO-A");
}
process.stdout.write(JSON.stringify(out));
"""


def _run(mode: str) -> dict:
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", SCRIPT, CORE, mode],
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def test_lane_shows_five_stages_in_order():
    html = _run("demo-slice")["demoHtml"]
    for stage in ("A", "B", "C", "VERIFIED", "DONE"):
        assert f'data-lane-stage="{stage}"' in html
    assert html.index('data-lane-stage="A"') < html.index('data-lane-stage="B"')
    assert html.index('data-lane-stage="B"') < html.index('data-lane-stage="C"')
    assert html.index('data-lane-stage="C"') < html.index('data-lane-stage="VERIFIED"')
    assert html.index('data-lane-stage="VERIFIED"') < html.index('data-lane-stage="DONE"')


def test_statuses_are_distinguishable_in_live():
    html = _run("live-slice")["liveHtml"]
    assert 'data-lane-stage="A" data-state="RUNNING"' in html
    assert 'data-lane-stage="B" data-state="BLOCKED"' in html
    assert 'data-lane-stage="VERIFIED" data-state="VERIFIED"' in html
    assert 'data-lane-stage="DONE" data-state="DONE"' in html


def test_demo_is_deterministic_labeled_and_never_green():
    res = _run("demo-slice")
    assert res["demoDeterministic"] is True
    html = res["demoHtml"]
    assert "badge-demo" in html and 'data-mode="demo"' in html
    assert "keine echte Courier-Ausführung" in html
    assert "#10b981" not in html
    assert 'data-lane-stage="VERIFIED" data-state="VERIFIED"' not in html


def test_live_ticker_and_detail_carry_proof():
    res = _run("live-slice")
    assert "badge-live" in res["liveHtml"]
    assert 'data-mode="live"' in res["liveHtml"]
    detail = res["detailHtml"]
    for label in ("Agent", "Workkey", "Owner", "Lease", "Status", "Zeitstempel", "Prüfnachweis"):
        assert label in detail
    assert "DEMO-A" in detail


def test_done_proof_uses_real_merge_evidence_not_synthetic_id():
    script = r"""
import { pathToFileURL } from "node:url";
const core = await import(pathToFileURL(process.argv[1]).href);
const snap = core.demoSnapshot();
snap.merged_prs.rows = [{ pr: 7, subject: "Land X", sha: "abc123",
  source: "git log integration/v1", at: "2026-10-18T00:00:00Z" }];
snap.muse_wall.stations[0].done = { value: "DONE",
  source: "git log integration/v1", at: "2026-10-18T00:00:00Z", pr: 7 };
const html = core.renderKolibri(snap, { mode: "live" });
process.stdout.write(JSON.stringify({ html }));
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script, CORE],
        capture_output=True,
        check=True,
    )
    html = json.loads(proc.stdout)["html"]
    assert "abc123" in html
    assert "evt:done:" not in html


def test_perf_guards_are_wired():
    assert PARTICLES.is_file()
    src = PARTICLES.read_text(encoding="utf-8")
    assert "PARTICLE_MAX = 64" in src
    assert "prefers-reduced-motion" in src
    assert "document.hidden" in src
    assert "requestAnimationFrame" in src
    assert "WebGL" not in src and "three" not in src.lower()
    assert '<canvas id="particles"' in HTML
    assert "initParticles" in JS and "document.hidden" in JS
    assert "#particles { display: none; }" in CSS
    assert ".lane-stage, .scroller ul" in CSS
