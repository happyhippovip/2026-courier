"""Red-Team R1 F4: CostGate must block unknown or invalid cost (UNKNOWN_COST=BLOCK)."""
import os
import sys

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.resource_policy import CostGate


@pytest.mark.parametrize("cost", [None, float("nan"), -1.0, float("-inf"), float("inf"), "0", True])
def test_cost_gate_blocks_unknown_or_invalid_cost(tmp_path, cost):
    kw = {} if cost is None else {"estimated_cost_eur": cost}
    res = CostGate.evaluate_spend_request("google_antigravity_plus", repo_dir=tmp_path, **kw)
    assert res["allowed"] is False


def test_cost_gate_still_allows_explicit_zero_for_active_resource(tmp_path):
    folder = tmp_path / "events" / "policies"
    folder.mkdir(parents=True)
    (folder / "resource_policy.json").write_text(
        '{"active_paid_resources":{"google_antigravity_plus":{"status":"ACTIVE_PAID"}}}',
        encoding="utf-8",
    )
    res = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=0.0, repo_dir=tmp_path)
    assert res["allowed"] is True
    assert res["reason"] == "AUTHORIZED_ACTIVE_RESOURCE"
