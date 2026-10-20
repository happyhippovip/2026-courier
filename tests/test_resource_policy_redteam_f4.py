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
    res = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=0.0, repo_dir=tmp_path)
    assert res["allowed"] is True
    assert res["reason"] == "AUTHORIZED_ACTIVE_RESOURCE"


def test_cost_gate_blocks_corrupt_or_missing_policy_file(tmp_path, monkeypatch):
    policy_dir = tmp_path / "events" / "policies"
    policy_dir.mkdir(parents=True)
    policy_file = policy_dir / "resource_policy.json"

    # 1. Corrupt JSON policy file -> BLOCKED
    policy_file.write_text("{corrupt json", encoding="utf-8")
    res_corrupt = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=0.0, repo_dir=tmp_path)
    assert res_corrupt["allowed"] is False
    assert res_corrupt["reason"] == "POLICY_MISSING_OR_CORRUPT"

    # 2. Empty JSON object policy file (missing active_paid_resources) -> BLOCKED
    policy_file.write_text("{}", encoding="utf-8")
    res_empty = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=0.0, repo_dir=tmp_path)
    assert res_empty["allowed"] is False
    assert res_empty["reason"] == "POLICY_MISSING_OR_CORRUPT"

    # 3. Missing policy file when require_policy_file=True -> BLOCKED
    policy_file.unlink()
    res_missing = CostGate.evaluate_spend_request(
        "google_antigravity_plus",
        estimated_cost_eur=0.0,
        repo_dir=tmp_path,
        require_policy_file=True,
    )
    assert res_missing["allowed"] is False
    assert res_missing["reason"] == "POLICY_MISSING_OR_CORRUPT"

