"""Kolibri flow fail-closed regression tests (V21/V22 QA findings).

No false VERIFIED-green without verifier evidence, without event_id, or on
replay. Four tests pin open product gaps in
courier_hub/static/kolibri_flow.mjs (visual lane owns the fix; this file
touches no product code). Three boundary tests guard behavior that is
already correct. Failures below are authentic product gaps, not bad tests.
"""

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FLOW = str(REPO / "courier_hub" / "static" / "kolibri_flow.mjs")


def _signals() -> dict:
    script = r"""
import { pathToFileURL } from "node:url";
const flow = await import(pathToFileURL(process.argv[1]).href);
const out = {
  no_id_verified_claim: flow.translateSignal({ verified: true, state: { value: "DONE" } }),
  string_verified: flow.translateSignal({ status: "VERIFIED", id: "qa-1" }),
  string_success: flow.translateSignal({ status: "SUCCESS", id: "qa-2" }),
  replay_first: flow.translateSignal({ verified: true, state: { value: "DONE" }, id: "replay-qa" }),
  replay_second: flow.translateSignal({ verified: true, state: { value: "DONE" }, id: "replay-qa" }),
  done_without_verifier: flow.translateSignal({ state: { value: "DONE" }, id: "qa-3" }),
  human_confirmed: flow.translateSignal({ status: "HUMAN_CONFIRMED", verified: false, id: "qa-4" }),
  demo_data: flow.translateSignal({ status: "DEMO", id: "qa-5" }),
};
process.stdout.write(JSON.stringify(out));
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script, FLOW],
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def test_no_green_without_event_id():
    sig = _signals()["no_id_verified_claim"]
    assert sig["event_id"] != "evt:gen:0", "synthetic id masks missing provenance"
    assert not (sig["state"] == "VERIFIED" and sig["verified"] is True)


def test_no_green_from_status_string_alone():
    sig = _signals()["string_verified"]
    assert sig["verified"] is False, "VERIFIED string is not verifier evidence"


def test_no_green_from_success_string_alone():
    sig = _signals()["string_success"]
    assert sig["verified"] is False, "SUCCESS string is not verifier evidence"


def test_replay_does_not_re_emit_success():
    sig = _signals()
    assert not (sig["replay_first"]["state"] == "VERIFIED"
                and sig["replay_second"]["state"] == "VERIFIED"), \
        "stateless re-emit: replay fires the green pulse again (needs seen-set)"


def test_done_without_verifier_stays_unknown():
    sig = _signals()["done_without_verifier"]
    assert (sig["state"], sig["verified"]) == ("UNKNOWN", False)


def test_human_confirmed_is_not_verified():
    sig = _signals()["human_confirmed"]
    assert (sig["state"], sig["verified"]) == ("UNKNOWN", False)


def test_demo_data_never_green():
    sig = _signals()["demo_data"]
    assert (sig["state"], sig["verified"]) == ("ROUTER", False)
