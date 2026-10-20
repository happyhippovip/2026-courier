import pytest
import os
import json
from pathlib import Path
from unittest import mock
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.resource_policy import (
    ResourcePolicyManager,
    CostGate,
    TaskLeaseManager,
    FileManifestTracker,
    TaskDedupeEngine,
    ChiefContextPackageBuilder
)

@pytest.fixture
def repo_dir(tmp_path):
    (tmp_path / "events" / "policies").mkdir(parents=True)
    (tmp_path / "events" / "locks").mkdir(parents=True)
    (tmp_path / "events" / "processed").mkdir(parents=True)
    return tmp_path

def test_resource_policy_manager_defaults(repo_dir):
    assert ResourcePolicyManager.get_default_builder() == "courier-antigravity-bridge"
    assert ResourcePolicyManager.get_default_reviewer() == "courier-codex-bridge"
    assert ResourcePolicyManager.get_default_iterations(repo_dir) == 1
    assert ResourcePolicyManager.is_resource_allowed("google_antigravity_plus", repo_dir) is True
    assert ResourcePolicyManager.is_resource_allowed("unknown_resource", repo_dir) is False

def test_resource_policy_manager_loaded(repo_dir):
    policy = {
        "schema_version": "2026.08.30-policy-v1",
        "active_paid_resources": {
            "my_resource": {"status": "ACTIVE_PAID"}
        },
        "operating_invariants": {
            "max_autonomous_iterations_per_task": 5
        }
    }
    policy_file = repo_dir / "events" / "policies" / "resource_policy.json"
    with open(policy_file, "w") as f:
        json.dump(policy, f)
        
    assert ResourcePolicyManager.get_default_iterations(repo_dir) == 5
    assert ResourcePolicyManager.is_resource_allowed("my_resource", repo_dir) is True

def _write_policy(repo_dir, policy):
    policy_file = repo_dir / "events" / "policies" / "resource_policy.json"
    policy_file.write_text(json.dumps(policy), encoding="utf-8")


def test_get_policy_rejects_unknown_or_changed_schema_version(repo_dir):
    """A policy file whose schema_version is not the accepted epoch is refused.

    The accepted epoch is the one in events/policies/resource_policy.json.
    Missing, foreign, and non-string versions must not authorize the file's
    resources. The same bytes stay refused on a second read.
    """
    from scripts.resource_policy import ACCEPTED_POLICY_SCHEMA, PolicyEpochError

    accepted = {
        "schema_version": ACCEPTED_POLICY_SCHEMA,
        "active_paid_resources": {"kept": {"status": "ACTIVE_PAID"}},
        "operating_invariants": {"max_autonomous_iterations_per_task": 2},
    }
    _write_policy(repo_dir, accepted)
    loaded = ResourcePolicyManager.get_policy(repo_dir)
    assert loaded["schema_version"] == ACCEPTED_POLICY_SCHEMA
    assert ResourcePolicyManager.is_resource_allowed("kept", repo_dir) is True
    assert ResourcePolicyManager.get_policy(repo_dir)["active_paid_resources"]["kept"]["status"] == "ACTIVE_PAID"

    foreign = {
        "schema_version": "2099.01.01-policy-v99",
        "active_paid_resources": {"synthetic_only": {"status": "ACTIVE_PAID"}},
        "operating_invariants": {"max_autonomous_iterations_per_task": 9},
    }
    for version in ("2099.01.01-policy-v99", None, "", 1, ["2026.08.30-policy-v1"]):
        body = dict(foreign)
        if version is None:
            body.pop("schema_version", None)
        else:
            body["schema_version"] = version
        _write_policy(repo_dir, body)
        with pytest.raises(PolicyEpochError, match="schema_version"):
            ResourcePolicyManager.get_policy(repo_dir)
        with pytest.raises(PolicyEpochError):
            ResourcePolicyManager.get_policy(repo_dir)
        assert ResourcePolicyManager.is_resource_allowed("synthetic_only", repo_dir) is False
        assert ResourcePolicyManager.get_default_iterations(repo_dir) == 1
        denied = CostGate.evaluate_spend_request("synthetic_only", repo_dir=repo_dir)
        assert denied["allowed"] is False
        assert denied["reason"] == "POLICY_EPOCH_REJECTED"
        assert denied["requires_human_gate"] is True


def test_cost_gate_evaluate_spend(repo_dir):
    res = CostGate.evaluate_spend_request("future_google_upgrade", repo_dir=repo_dir)
    assert not res["allowed"]
    assert res["reason"] == "RESOURCE_PLANNED_NOT_ACTIVE"

    res = CostGate.evaluate_spend_request("on_demand_api_tiers", repo_dir=repo_dir)
    assert not res["allowed"]
    assert res["reason"] == "UNAUTHORIZED_RESOURCE_TIER"

    res = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=10.0, repo_dir=repo_dir)
    assert not res["allowed"]
    assert res["reason"] == "SPEND_NOT_ALLOWED_BY_POLICY"

    res = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=0.0, repo_dir=repo_dir)
    assert res["allowed"]
    assert res["reason"] == "AUTHORIZED_ACTIVE_RESOURCE"

def test_task_lease_manager(repo_dir):
    tlm = TaskLeaseManager(repo_dir)
    success, reason, data = tlm.acquire_lease("task1", "hash1", "ownerA", duration_sec=10)
    assert success
    assert tlm.is_task_claimed("task1") is True
    
    success, reason, data = tlm.acquire_lease("task1", "hash1", "ownerB", duration_sec=10)
    assert not success
    
    success, reason, data = tlm.acquire_lease("task1", "hash1", "ownerA", duration_sec=20)
    assert success
    
    assert tlm.release_lease("task1", "ownerB") is False
    assert tlm.release_lease("task1", "ownerA") is True
    assert tlm.is_task_claimed("task1") is False

def test_file_manifest_tracker(repo_dir):
    test_file = repo_dir / "test.txt"
    test_file.write_text("hello world")
    h = FileManifestTracker.get_file_hash(test_file)
    assert h != "FILE_NOT_FOUND"
    
    assert FileManifestTracker.is_file_unchanged(test_file, h) is True
    assert FileManifestTracker.is_file_unchanged(test_file, "wrong_hash") is False
    
    manifest = FileManifestTracker.build_manifest(["test.txt"], repo_dir)
    assert manifest["test.txt"] == h
    
def test_task_dedupe_engine(repo_dir):
    engine = TaskDedupeEngine(repo_dir)
    test_file = repo_dir / "test.txt"
    test_file.write_text("hello world")
    
    task_hash = engine.compute_task_hash(
        "type", "instruction", "agent", ["test.txt"], {"param": 1}
    )
    
    assert engine.get_cached_result(task_hash) is None
    
    result_payload = {"payload": {"status": "ok"}}
    result_file = "res1.json"
    (repo_dir / "events" / "processed" / result_file).write_text(json.dumps(result_payload))
    
    import hashlib
    res_hash = hashlib.sha256(json.dumps(result_payload["payload"], sort_keys=True).encode("utf-8")).hexdigest()
    
    engine.register_task_result(task_hash, "task1", result_file, res_hash)
    
    cached = engine.get_cached_result(task_hash)
    assert cached is not None
    assert cached["reused_from_cache"] is True
    assert cached["result_hash"] == res_hash

    tampered_payload = {"payload": {"status": "tampered"}}
    (repo_dir / "events" / "processed" / result_file).write_text(json.dumps(tampered_payload))
    assert engine.get_cached_result(task_hash) is None

def test_chief_context_package_builder(repo_dir):
    # Setup test file
    test_file = repo_dir / "scope.txt"
    test_file.write_text("scope data")
    
    pkg = ChiefContextPackageBuilder.build_compact_package(
        workflow_id="wf1",
        task_id="t1",
        instruction="do it",
        scope_files=["scope.txt"],
        context_version=1,
        context_delta={"some": "delta"},
        repo_dir=repo_dir
    )
    
    assert pkg["workflow_id"] == "wf1"
    assert pkg["task_id"] == "t1"
    assert pkg["instruction"] == "do it"
    assert pkg["context_version"] == "v1"
    assert pkg["context_delta"] == {"some": "delta"}
    assert "file_manifest" in pkg
    assert "scope.txt" in pkg["file_manifest"]
    assert pkg["file_manifest"]["scope.txt"] != "FILE_NOT_FOUND"

def test_review_dedupe_tracker():
    from scripts.resource_policy import ReviewDedupeTracker
    res, msg = ReviewDedupeTracker.should_review("hashA", "hashA")
    assert res is False
    assert msg == "RESULT_HASH_UNCHANGED_SKIP_REDUNDANT_REVIEW"
    
    res, msg = ReviewDedupeTracker.should_review("hashA", "hashB")
    assert res is True
    assert msg == "NEW_OR_MODIFIED_RESULT_REVIEW_REQUIRED"
    
    res, msg = ReviewDedupeTracker.should_review(None, "hashB")
    assert res is True
    assert msg == "NEW_OR_MODIFIED_RESULT_REVIEW_REQUIRED"

def test_task_dedupe_engine_missing_expected_hash(repo_dir):
    engine = TaskDedupeEngine(repo_dir)
    test_file = repo_dir / "test.txt"
    test_file.write_text("hello world")
    
    task_hash = engine.compute_task_hash(
        "type", "instruction", "agent", ["test.txt"], {"param": 1}
    )
    
    result_payload = {"payload": {"status": "ok"}}
    result_file = "res1.json"
    (repo_dir / "events" / "processed" / result_file).write_text(json.dumps(result_payload))
    
    # Register with empty hash
    engine.register_task_result(task_hash, "task1", result_file, "")
    
    cached = engine.get_cached_result(task_hash)
    assert cached is None
