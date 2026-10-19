import json
import subprocess
from pathlib import Path
from courier_hub.kolibri_data import build_snapshot, read_arbitrage_research

REPO = Path(__file__).resolve().parents[2]
CORE = str(REPO / "courier_hub" / "static" / "kolibri_core.mjs")


def test_read_arbitrage_research_structure():
    root = REPO
    data = read_arbitrage_research(root, observed_at="2026-10-18T12:00:00Z")
    assert data["available"] is True
    assert "simulation" in data
    assert data["simulation"]["net_simulated_profit_eur"] > 0
    assert data["simulation"]["status"] == "SIMULATED (NO REAL TRADES)"
    assert data["verified_actual_revenue"]["amount_eur"] == 0.00
    assert len(data["pairs_monitored"]) >= 1


def test_build_snapshot_contains_arbitrage_research():
    root = REPO
    # hub can be None; readers fail gracefully
    snapshot = build_snapshot(None, root=root, observed_at="2026-10-18T12:00:00Z")
    assert "arbitrage_research" in snapshot
    arbi = snapshot["arbitrage_research"]
    assert arbi["available"] is True
    assert arbi["verified_actual_revenue"]["amount_eur"] == 0.00
    assert arbi["simulation"]["net_simulated_profit_eur"] > 0


def test_kolibri_dom_renders_arbi_first_before_system_resources():
    script = r"""
import { pathToFileURL } from "node:url";
const core = await import(pathToFileURL(process.argv[1]).href);
const demo = core.demoSnapshot();
const html = core.renderKolibri(demo, { mode: "demo" });
const arbiIdx = html.indexOf('id="arbitrage-research"');
const sysIdx = html.indexOf('id="system-resources"');
const out = {
  hasArbi: arbiIdx !== -1,
  hasSys: sysIdx !== -1,
  arbiBeforeSys: arbiIdx !== -1 && sysIdx !== -1 && arbiIdx < sysIdx,
  hasBadge: html.includes("REAL_TRADES=0"),
  hasVerifiedRev: html.includes("0.00 EUR"),
};
process.stdout.write(JSON.stringify(out));
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script, CORE],
        capture_output=True,
        check=True,
        text=True,
    )
    res = json.loads(proc.stdout)
    assert res["hasArbi"] is True
    assert res["hasSys"] is True
    assert res["arbiBeforeSys"] is True
    assert res["hasBadge"] is True
    assert res["hasVerifiedRev"] is True
