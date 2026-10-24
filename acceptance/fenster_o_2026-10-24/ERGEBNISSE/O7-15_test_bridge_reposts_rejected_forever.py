"""O7-15 (G2 / R1): the bridge re-posts a controller-refused mission without bound.

scripts/ledger_v1_bridge.py:342-369 (base 81bbf224): the mapping is stored with
posted=False (:342-362), _post_task (:713-745) turns every non-2xx/non-5xx answer
into {"rejected": True}, and :366-369 only emits ``skipped/rejected`` and
continues. Nothing stamps BLOCKED, nothing counts attempts: every pass posts the
same refused task again, forever. Same pin as V43 R1
(acceptance/v43_2026-10-24/V43_bridge_refusal_park_pin.diff), here against the base
with a generic 400 (with PR #846 the same happens for 400 cost_blocked).
"""
import json

import pytest

from tests.test_ledger_v1_bridge import FakeHTTP, _home, _ready, _run, _seed, _spec


class RefusingHTTP(FakeHTTP):
    def __call__(self, method, url, headers, body, timeout):
        if method == "POST" and url.endswith("/v1/tasks"):
            self.posts.append(json.loads(body.decode("utf-8")))
            return 400, b'{"error":"invalid_request","message":"refused by the controller"}'
        return super().__call__(method, url, headers, body, timeout)


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="O7-15/G2: a 4xx-refused mission is posted again on every pass")
def test_refused_mission_is_blocked_and_not_posted_again(tmp_path):
    http = RefusingHTTP()
    home = _home(tmp_path, {"A": _spec()})
    _seed(home, [_ready("A", "a-assign")])
    for _ in range(3):
        _run(home, http)
    mission = json.loads((home / "ledger_bridge_state.json").read_text(encoding="utf-8"))["missions"]["A"]
    assert len(http.posts) == 1, f"{len(http.posts)} POSTs for one refused mission"
    assert mission.get("status") == "BLOCKED", mission


def test_guard_duplicate_post_is_not_a_refusal(tmp_path):
    """A replayed POST that the controller answers as duplicate (200) is posted, not refused."""
    http = FakeHTTP()
    home = _home(tmp_path, {"A": _spec()})
    _seed(home, [_ready("A", "a-assign")])
    _run(home, http)
    _run(home, http)
    mission = json.loads((home / "ledger_bridge_state.json").read_text(encoding="utf-8"))["missions"]["A"]
    assert len(http.posts) == 1 and mission["posted"] is True and mission["status"] == "POSTED"
