"""[DRUIDE | ACCOUNT 2] K9: test gaps found by the K1 mutation sweep (survivors that are NOT equivalent). No change to the tools.

Every test here kills at least one sweep mutant (see deliver/MUTATION_K9.txt); the mutant ids are named in the test comments.
"""

import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ci_watcher_v2 import SHA  # noqa: E402
from tools.automation import ci_watcher_v2 as w  # noqa: E402


def iso(epoch):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def dispatched(at):
    return {"dispatch": "DISPATCHED", "dispatched_at": at}


# --- DISPATCH_SKEW (sweep ci_watcher_v2:97 5.0->6.0, :427 Lt->LtE) -------------------------------------------------

def test_k9_a_run_created_exactly_skew_seconds_before_our_dispatch_is_ours_and_one_second_more_is_not():
    at = 1_800_000_000.0
    edge, too_old = {"id": 1, "createdAt": iso(at - 5)}, {"id": 2, "createdAt": iso(at - 6)}
    ours, ok = w.select_runs([edge, too_old], dispatched(at))
    assert w.DISPATCH_SKEW == 5.0 and ok is True
    assert [run["id"] for run in ours] == [1]  # exactly at the floor stays ours (not `<=`), 6 s before is never ours (not a 6 s skew)


def test_k9_a_run_created_just_below_the_floor_is_not_ours():
    at = 1_800_000_000.5
    assert w.select_runs([{"id": 1, "createdAt": iso(at - 5.5)}], dispatched(at))[0] == []  # floor 1_799_999_995.5, created 1_799_999_995


# --- the HTTP status boundaries of "provably rejected" (sweep :618 LtE->Lt, 400->401) --------------------------------

@pytest.mark.parametrize("status,rejected", [(399, False), (400, True), (401, True), (404, True), (407, True), (408, False), (409, True),
                                              (422, True), (499, True), (500, False), (502, False)])
def test_k9_only_http_4xx_other_than_408_proves_that_github_did_not_accept_the_dispatch(status, rejected):
    assert w._rejected_before_acceptance(1, f"gh: Not Found (HTTP {status})") is rejected


# --- the one-shot results of --reset-state report 0 polls (sweep :450 :452 :459 :463) -----------------------------------

def reset(tmp_path):
    return w.reset_state("WK", SHA, tmp_path)


def state_file(tmp_path):
    return w.state_path(Path(tmp_path), w.idempotency_key("WK", SHA))


def test_k9_reset_results_report_zero_polls_and_the_matching_exit_codes(tmp_path):
    out = reset(tmp_path)
    assert (out["status"], out["polls_this_call"]) == ("NO_STATE", 0)
    path = state_file(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ not json")
    out = reset(tmp_path)
    assert (out["status"], out["polls_this_call"]) == (w.STATE_UNREADABLE, 0)
    path.write_text(json.dumps({"attempts": 3, "dispatch": "NONE", "status": w.WATCHING}))
    out = reset(tmp_path)
    assert (out["status"], out["polls_this_call"]) == (w.RESET_REFUSED, 0) and "COMPLETED/EXHAUSTED" in out["last_error"]
    path.write_text(json.dumps({"attempts": 3, "dispatch": "NONE", "status": w.COMPLETED}))
    out = reset(tmp_path)
    assert (out["status"], out["polls_this_call"], out["attempts"]) == ("RESET", 0, 0)
    assert json.loads(path.read_text())["status"] == w.WATCHING
