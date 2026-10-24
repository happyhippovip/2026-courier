"""O7-06 (B3): nothing is recorded as accepted before the verifier's RESULT_ACCEPTED.

Only the verifier sets accepted_result_id (courier_core/state_machine.py, RESULT_ACCEPTED).
The bridge, however, stores whatever result id the controller view shows in the
mapping field ``accepted_result_id``: for a view that is not COMPLETE, _result_id
(scripts/ledger_v1_bridge.py:537-548) falls back to ``result_id`` / ``pending_result_id``,
and _dispatch writes it at scripts/ledger_v1_bridge.py:373-377 (and _feedback at :232).
A state without ``status`` then derives FINAL_DONE from that field
(_derive_mission_status, ledger_v1_bridge.py:927-934; courier_hub/automation_status.py:156-160).
Guard (holds): a COMPLETE view without resolution=verified never emits FINAL.
"""
import json

import pytest

from scripts.ledger_v1_bridge import _load_state
from tests.test_ledger_v1_bridge import FakeHTTP, _home, _ready, _run, _seed, _spec


class PendingHTTP(FakeHTTP):
    """After the POST the controller shows a RUNNING task with a pending (unverified) result."""

    def __call__(self, method, url, headers, body, timeout):
        reply = super().__call__(method, url, headers, body, timeout)
        for view in self.views.values():
            view.update(status="RUNNING", attempt=1, pending_result_id="res-pending")
        return reply


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="O7-06/B3: bridge stores a pending result id as accepted_result_id")
def test_pending_result_is_not_recorded_as_accepted(tmp_path):
    http = PendingHTTP()
    home = _home(tmp_path, {"A": _spec()})
    _seed(home, [_ready("A", "a-assign")])
    _run(home, http)
    _run(home, http)
    state_path = home / "ledger_bridge_state.json"
    mapping = json.loads(state_path.read_text(encoding="utf-8"))["missions"]["A"]
    assert mapping["status"] == "POSTED"
    # Expected after a fix: no RESULT_ACCEPTED yet -> accepted_result_id stays None, and a
    # status-less copy of this mapping can never derive FINAL_DONE.
    legacy = {k: v for k, v in mapping.items() if k not in ("status", "reason")}
    state_path.write_text(json.dumps({"missions": {"A": legacy}}), encoding="utf-8")
    derived = _load_state(state_path)["missions"]["A"].get("status")
    assert mapping["accepted_result_id"] is None and derived != "FINAL_DONE", (mapping, derived)


def test_guard_complete_without_verified_resolution_is_not_final(tmp_path):
    http = FakeHTTP()
    home = _home(tmp_path, {"A": _spec()})
    _seed(home, [_ready("A", "a-assign")])
    _run(home, http)
    for view in http.views.values():
        view.update(status="COMPLETE", attempt=1, accepted_result_id="res-1", resolution="effect_confirmed")
    _code, out, _err, _log, lines = _run(home, http)
    assert not any('"FINAL"' in line for line in lines)
    assert '"outcome": "final"' not in out
