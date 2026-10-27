"""P2b: the bridge maps RESULT_ACCEPTED / accepted_result_id to a journal proof.

Injected HTTP only; no providers, no network, 0 EUR.
"""

import hashlib
import json
import re

import pytest

from scripts.ledger_v1_bridge import journal_proof
from tests.test_ledger_v1_bridge import (
    FakeHTTP, _finals, _home, _ready, _run, _seed, _spec, _state,
)

# Same acceptance rule as the P2 queue release draft (PATCH_P2_QUEUE_FEED_PROOF).
P2_PROOF = re.compile(
    r"^(journal:[0-9]+:RESULT_ACCEPTED(\|sha256:[0-9a-f]{64})?|local-verified:sha256:[0-9a-f]{64})$")
A = "a" * 64
B = "b" * 64


def _result(**over):
    body = {"task_id": "t", "attempt": 1, "result_id": "result-a", "accepted_seq": 7,
            "artifacts": [{"path": "out.txt", "sha256": B}]}
    body.update(over)
    return body


def test_single_artifact_proof_matches_p2_format():
    proof = journal_proof(_result(), "result-a")
    assert proof == "journal:7:RESULT_ACCEPTED|sha256:" + B
    assert P2_PROOF.match(proof)


def test_no_artifacts_gives_seq_only_proof():
    proof = journal_proof(_result(artifacts=[]), "result-a")
    assert proof == "journal:7:RESULT_ACCEPTED"
    assert P2_PROOF.match(proof)


def test_multi_artifact_digest_is_order_independent():
    one = journal_proof(_result(artifacts=[{"path": "a", "sha256": A}, {"path": "b", "sha256": B}]), "result-a")
    two = journal_proof(_result(artifacts=[{"path": "b", "sha256": B}, {"path": "a", "sha256": A}]), "result-a")
    canon = json.dumps([{"path": "a", "sha256": A}, {"path": "b", "sha256": B}], sort_keys=True, separators=(",", ":"))
    assert one == two == "journal:7:RESULT_ACCEPTED|sha256:" + hashlib.sha256(canon.encode()).hexdigest()
    assert P2_PROOF.match(one)


@pytest.mark.parametrize("over,accepted", [
    ({"accepted_seq": None}, "result-a"),
    ({"accepted_seq": 0}, "result-a"),
    ({"accepted_seq": -3}, "result-a"),
    ({"accepted_seq": True}, "result-a"),
    ({"accepted_seq": "7"}, "result-a"),
    ({}, "result-b"),
    ({}, None),
    ({}, ""),
])
def test_missing_or_mismatched_identity_is_not_proven(over, accepted):
    assert journal_proof(_result(**over), accepted) is None


def test_non_dict_result_is_not_proven():
    assert journal_proof(None, "result-a") is None
    assert journal_proof([], "result-a") is None


def test_malformed_artifact_digest_is_dropped_not_invented():
    proof = journal_proof(_result(artifacts=[{"path": "x", "sha256": "XYZ"}]), "result-a")
    assert proof == "journal:7:RESULT_ACCEPTED"


class _ResultHTTP(FakeHTTP):
    """FakeHTTP plus GET /v1/tasks/<id>/result like courier_core.Controller.task_result."""

    def __init__(self):
        super().__init__()
        self.results = {}
        self.result_gets = 0

    def __call__(self, method, url, headers, body, timeout):
        if method == "GET" and url.rstrip("/").endswith("/result"):
            self.result_gets += 1
            task_id = url.rstrip("/").rsplit("/", 2)[-2]
            result = self.results.get(task_id)
            if result is None:
                return 409, b'{"error":"not_verified"}'
            return 200, json.dumps(result).encode()
        return super().__call__(method, url, headers, body, timeout)


def _posted_then_complete(tmp_path, http):
    home = _home(tmp_path, {"A": _spec()})
    _seed(home, [_ready("A", "a-assign")])
    assert _run(home, http)[0] == 0
    task_id = _state(home)["A"]["task_id"]
    http.views[task_id].update({"status": "COMPLETE", "attempt": 1,
                                "accepted_result_id": "result-a", "resolution": "verified"})
    return home, task_id


def test_final_done_carries_journal_proof_and_replay_is_stable(tmp_path):
    http = _ResultHTTP()
    home, task_id = _posted_then_complete(tmp_path, http)
    http.results[task_id] = _result(task_id=task_id)
    code, out, err, log, lines = _run(home, http)
    assert code == 0, err
    done = _state(home)["A"]
    assert done["status"] == "FINAL_DONE"
    assert done["journal_proof"] == "journal:7:RESULT_ACCEPTED|sha256:" + B
    assert P2_PROOF.match(done["journal_proof"])
    frozen = (home / "ledger_bridge_state.json").read_text(encoding="utf-8")
    assert _run(home, http)[0] == 0
    assert (home / "ledger_bridge_state.json").read_text(encoding="utf-8") == frozen
    assert len(_finals(home)) == 1


def test_final_done_without_result_proof_has_no_journal_proof(tmp_path):
    http = _ResultHTTP()
    home, task_id = _posted_then_complete(tmp_path, http)
    assert _run(home, http)[0] == 0
    done = _state(home)["A"]
    assert done["status"] == "FINAL_DONE"
    assert "journal_proof" not in done
    assert len(_finals(home)) == 1


def test_result_for_other_result_id_is_not_proof(tmp_path):
    http = _ResultHTTP()
    home, task_id = _posted_then_complete(tmp_path, http)
    http.results[task_id] = _result(task_id=task_id, result_id="result-other")
    assert _run(home, http)[0] == 0
    assert "journal_proof" not in _state(home)["A"]


def test_missing_proof_is_backfilled_once_without_second_final(tmp_path):
    http = _ResultHTTP()
    home, task_id = _posted_then_complete(tmp_path, http)
    assert _run(home, http)[0] == 0
    assert "journal_proof" not in _state(home)["A"]
    http.results[task_id] = _result(task_id=task_id, accepted_seq=12)
    assert _run(home, http)[0] == 0
    filled = _state(home)["A"]
    assert filled["status"] == "FINAL_DONE"
    assert filled["journal_proof"] == "journal:12:RESULT_ACCEPTED|sha256:" + B
    assert len(_finals(home)) == 1
    gets = http.result_gets
    frozen = (home / "ledger_bridge_state.json").read_text(encoding="utf-8")
    assert _run(home, http)[0] == 0
    assert http.result_gets == gets  # proven missions are not re-queried
    assert (home / "ledger_bridge_state.json").read_text(encoding="utf-8") == frozen


def test_result_endpoint_down_keeps_final_done_unproven(tmp_path):
    http = _ResultHTTP()
    home, task_id = _posted_then_complete(tmp_path, http)

    class _Down(_ResultHTTP):
        pass

    original = http.__class__.__call__

    def flaky(self, method, url, headers, body, timeout):
        if method == "GET" and url.rstrip("/").endswith("/result"):
            return 503, b'{"error":"busy"}'
        return original(self, method, url, headers, body, timeout)

    _Down.__call__ = flaky
    down = _Down()
    down.posts, down.views = http.posts, http.views
    assert _run(home, down)[0] == 0
    done = _state(home)["A"]
    assert done["status"] == "FINAL_DONE"
    assert "journal_proof" not in done
    assert len(_finals(home)) == 1
