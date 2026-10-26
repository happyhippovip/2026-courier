"""[DRUIDE | ACCOUNT 2] K4: the watcher against the REAL shape of `gh run list --json ...`.

The two fixtures are verbatim output of two real read-only queries (2 of the allowed 3, 27.10.2026 ~01:00 Berlin):
  gh run list --repo happyhippovip/2026-courier --commit 26ee2348... --limit 20 --json <FIELDS>   (event "push")
  gh run list --repo happyhippovip/2026-courier --commit 90a34fb1... --limit 20 --json <FIELDS>   (event "pull_request")
Everything else here is derived from them and labelled CONSTRUCTED. No network in the tests.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ci_watcher_v2 import Clock, Gh, go, state_of  # noqa: E402
from tools.automation import ci_watcher_v2 as w  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
PUSH_SHA = "26ee23485952e61f6f2ad3da24176d6bbac82a63"
PR_SHA = "90a34fb1ec6e10dadafb8b647521c1921cfa8ab9"
PUSH = json.loads((FIX / "gh_run_list_push_26ee2348.json").read_text())
PR = json.loads((FIX / "gh_run_list_pull_request_90a34fb1.json").read_text())


@pytest.mark.parametrize("data", [PUSH, PR], ids=["push", "pull_request"])
def test_k4_real_output_has_exactly_the_requested_fields_with_the_expected_types(data):
    wanted = set(w.FIELDS.split(","))
    assert data and all(set(item) == wanted for item in data)
    for item in data:
        assert isinstance(item["databaseId"], int) and not isinstance(item["databaseId"], bool)
        assert item["status"] == "completed" and item["conclusion"] == "success"
        assert w._epoch(item["createdAt"]) is not None and item["url"].startswith("https://github.com/")


@pytest.mark.parametrize("data, sha", [(PUSH, PUSH_SHA), (PR, PR_SHA)], ids=["push", "pull_request"])
def test_k4_list_runs_accepts_real_output_and_drops_foreign_shas(data, sha):
    assert w.list_runs(sha, Gh(data)) == data
    assert w.list_runs("f" * 40, Gh(data)) == []  # every run's headSha differs from the asked commit
    mixed = data + [dict(data[0], databaseId=1, headSha="c" * 40)]
    assert w.list_runs(sha, Gh(mixed)) == data


@pytest.mark.parametrize("data, sha", [(PUSH, PUSH_SHA), (PR, PR_SHA)], ids=["push", "pull_request"])
def test_k4_observer_mode_confirms_real_finished_runs_as_success_after_two_identical_looks(tmp_path, data, sha):
    result = go(tmp_path, Gh(data), sha=sha, window=60, base=1, max_interval=1)
    assert result["status"] == w.COMPLETED and result["outcome"] == "SUCCESS" and result["exit_code"] == 0
    assert result["polls_this_call"] >= 2  # never a verdict on one look
    assert sorted(str(r["databaseId"]) for r in result["runs"]) == sorted(str(i["databaseId"]) for i in data)


def test_k4_dispatch_mode_never_adopts_real_push_or_pull_request_runs(tmp_path):
    """Real runs from before the dispatch (and of another event) are not ours: no false SUCCESS, DISPATCH_UNCONFIRMED."""
    clock = Clock()  # far later than the real createdAt values
    result = go(tmp_path, Gh(PUSH), clock, sha=PUSH_SHA, dispatch=lambda: None, window=60, base=1, max_interval=1, dispatch_grace=5)
    assert result["status"] == w.UNCONFIRMED and result["outcome"] != "SUCCESS"


def test_k4_constructed_real_shape_runs_created_after_the_dispatch_but_of_event_push_are_not_ours(tmp_path):
    clock = Clock()  # CONSTRUCTED: real shape, createdAt moved after the dispatch
    later = copy.deepcopy(PUSH)
    for item in later:
        item["createdAt"] = w_iso(clock.t + 2)
    result = go(tmp_path, Gh(later), clock, sha=PUSH_SHA, dispatch=lambda: None, window=60, base=1, max_interval=1, dispatch_grace=5)
    assert result["status"] == w.UNCONFIRMED


def test_k4_constructed_same_runs_as_workflow_dispatch_after_the_dispatch_are_ours_and_decide(tmp_path):
    clock = Clock()
    mine = copy.deepcopy(PUSH)
    for item in mine:
        item["createdAt"], item["event"] = w_iso(clock.t + 2), "workflow_dispatch"
    result = go(tmp_path, Gh(mine), clock, sha=PUSH_SHA, dispatch=lambda: None, window=60, base=1, max_interval=1)
    assert result["status"] == w.COMPLETED and result["outcome"] == "SUCCESS"


def test_k4_constructed_an_older_workflow_dispatch_run_of_the_same_sha_is_not_ours(tmp_path):
    clock = Clock()
    older = copy.deepcopy(PUSH)
    for item in older:
        item["createdAt"], item["event"] = w_iso(clock.t - 3600), "workflow_dispatch"  # an hour BEFORE our dispatch
    result = go(tmp_path, Gh(older), clock, sha=PUSH_SHA, dispatch=lambda: None, window=60, base=1, max_interval=1, dispatch_grace=5)
    assert result["status"] == w.UNCONFIRMED


@pytest.mark.parametrize("conclusion", ["", None])
def test_k4_constructed_unfinished_run_with_empty_conclusion_is_never_success(tmp_path, conclusion):
    """gh prints "" (REPORTED, not observed by me) or null for the conclusion of a run that has not finished."""
    running = copy.deepcopy(PUSH)
    running[0].update(status="in_progress", conclusion=conclusion)
    result = go(tmp_path, Gh(running), sha=PUSH_SHA, window=10, base=1, max_interval=1)
    assert result["status"] == w.WAITING and result["outcome"] != "SUCCESS"


def test_k4_constructed_a_failed_real_shape_run_is_finished_not_success(tmp_path):
    failed = copy.deepcopy(PUSH)
    failed[1].update(conclusion="failure")
    result = go(tmp_path, Gh(failed), sha=PUSH_SHA, window=60, base=1, max_interval=1)
    assert result["outcome"] == "FINISHED_NOT_SUCCESS" and result["exit_code"] == 1


def test_k4_an_empty_list_from_gh_is_not_a_result(tmp_path):
    """Real fact (5 earlier queries on acc2/automation-v2-fixes): a commit without CI gives []. Never SUCCESS."""
    result = go(tmp_path, Gh([]), window=10, base=1, max_interval=1)
    assert result["status"] == w.WAITING and result["outcome"] != "SUCCESS" and state_of(tmp_path)["runs"] == []


def w_iso(epoch):
    from test_ci_watcher_v2 import iso
    return iso(epoch)
