import pytest
import sys
import copy
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from scripts.courier_continue import execute_task, compute_frontier
from scripts.agent_handoff_ledger import (
    freshness,
    load_bundle,
    update,
    validate_bundle,
    LedgerError,
)
from tests.test_agent_handoff_ledger import initialize, guard as mock_guard


def test_warhead_a_false_external_success():
    """WARHEAD A: FALSE_EXTERNAL_SUCCESS must fail closed for all unauthorized external effects."""
    unauthorized_edges = [
        ("RELEASE", "UNVERIFIED_EXTERNAL_EFFECT_RELEASE"),
        ("PUBLIC DEPLOYMENT", "UNVERIFIED_EXTERNAL_EFFECT_PUBLIC DEPLOYMENT"),
        ("PUBLIC_DEPLOYMENT", "UNVERIFIED_EXTERNAL_EFFECT_PUBLIC_DEPLOYMENT"),
        ("FIRST PILOT", "UNVERIFIED_EXTERNAL_EFFECT_FIRST PILOT"),
        ("FIRST_PILOT", "UNVERIFIED_EXTERNAL_EFFECT_FIRST_PILOT"),
        ("PAYMENT ONLY WHEN ACTUALLY REQUIRED", "MONEY_REQUIRED_PAYMENT_PROOF"),
        ("PAYMENT_ONLY_WHEN_ACTUALLY_REQUIRED", "MONEY_REQUIRED_PAYMENT_PROOF"),
        ("ONBOARD_FIRST_PILOT_CUSTOMER", "HUMAN_REQUIRED_PILOT_ONBOARDING"),
        ("EXTERNAL_PUBLICATION", "UNVERIFIED_EXTERNAL_EFFECT_EXTERNAL_PUBLICATION"),
        ("PILOT INTAKE", "UNVERIFIED_EXTERNAL_EFFECT_PILOT INTAKE"),
        ("PILOT_INTAKE", "UNVERIFIED_EXTERNAL_EFFECT_PILOT_INTAKE"),
        ("PILOT INTAKE", "UNVERIFIED_EXTERNAL_EFFECT_PILOT INTAKE"),
        ("PILOT_INTAKE", "UNVERIFIED_EXTERNAL_EFFECT_PILOT_INTAKE"),
        ("ARBITRARY_TASK_NAME", "UNRECOGNIZED_OR_UNVERIFIED_TASK_ARBITRARY_TASK_NAME"),
    ]

    for edge_name, expected_blocker in unauthorized_edges:
        task = {"instruction": f"Run {edge_name}", "edge_name": edge_name}
        res_task, success, blocker = execute_task(task, "non_existent.json", {})
        assert not success, f"Warhead A failed: {edge_name} unexpectedly succeeded"
        assert blocker == expected_blocker, f"Warhead A failed: {edge_name} blocker mismatch: got {blocker}, expected {expected_blocker}"

    # PR41 ACCEPTANCE fails closed when not an ancestor
    with patch("subprocess.check_output", side_effect=Exception("not an ancestor")):
        task = {"instruction": "Prove PR41", "edge_name": "PR41 ACCEPTANCE"}
        res_task, success, blocker = execute_task(task, "non_existent.json", {})
        assert not success, "Warhead A failed: PR41 ACCEPTANCE succeeded without merge ancestry"
        assert blocker == "UNVERIFIED_EXTERNAL_EFFECT_PR41 ACCEPTANCE"

    # LEDGER/HANDOFF fails closed when ledger file missing or corrupted
    task = {"instruction": "Prove LEDGER/HANDOFF", "edge_name": "LEDGER/HANDOFF"}
    res_task, success, blocker = execute_task(task, "non_existent_path.json", {})
    assert not success, "Warhead A failed: LEDGER/HANDOFF succeeded without valid ledger"
    assert blocker == "UNVERIFIED_EXTERNAL_EFFECT_LEDGER/HANDOFF"


def test_warhead_b_self_generated_or_replayed_evidence(tmp_path):
    """WARHEAD B: SELF_GENERATED_OR_REPLAYED_EVIDENCE must fail closed."""
    ledger = tmp_path / "ledger_warhead_b.json"
    initialize(ledger)
    with open(ledger, "r") as f:
        bundle = json.load(f)
    current_sha = bundle["record"]["CURRENT_SHA"]
    current_runtime = bundle["record"]["RUNTIME_IDENTITY"]
    bundle["acceptance_guard"] = mock_guard(sha=current_sha, runtime_identity=current_runtime)

    # Sub-case 1: Caller-created evidence (producer_id == 'Google-Antigravity' or updated_by)
    guard_caller = copy.deepcopy(bundle["acceptance_guard"])
    guard_caller["evidence"].append({
        "source_url": "https://example.com/caller_ev",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": "2026-09-22T16:14:56Z",
        "evidence_sha": current_sha,
        "runtime_binding": current_runtime,
        "validity": "VALID",
        "reason": "forged",
        "producer_id": "Google-Antigravity",
        "verifier_id": "VERIFIER-01",
    })
    with pytest.raises(LedgerError) as exc:
        update(ledger, bundle["revision"], {"STATUS": "READY"}, "Google-Antigravity", 5.0, guard_caller)
    assert "caller-created" in str(exc.value)

    # Sub-case 2: Self-certifying evidence (producer_id == verifier_id)
    guard_self = copy.deepcopy(bundle["acceptance_guard"])
    guard_self["evidence"].append({
        "source_url": "https://example.com/self_ev",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": "2026-09-22T16:14:56Z",
        "evidence_sha": current_sha,
        "runtime_binding": current_runtime,
        "validity": "VALID",
        "reason": "self",
        "producer_id": "VERIFIER-01",
        "verifier_id": "VERIFIER-01",
    })
    with pytest.raises(LedgerError) as exc:
        update(ledger, bundle["revision"], {"STATUS": "READY"}, "Other-Writer", 5.0, guard_self)
    assert "decision path" in str(exc.value) or "independent" in str(exc.value)

    # Sub-case 3: Missing producer_id or verifier_id
    guard_missing = copy.deepcopy(bundle["acceptance_guard"])
    guard_missing["evidence"].append({
        "source_url": "https://example.com/missing_ev",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": "2026-09-22T16:14:56Z",
        "evidence_sha": current_sha,
        "runtime_binding": current_runtime,
        "validity": "VALID",
        "reason": "missing",
    })
    with pytest.raises(LedgerError) as exc:
        update(ledger, bundle["revision"], {"STATUS": "READY"}, "Other-Writer", 5.0, guard_missing)
    assert "unverifiable producer or verifier" in str(exc.value)

    # Sub-case 4: Verifier == ledger writer (verifier_id == updated_by)
    guard_writer = copy.deepcopy(bundle["acceptance_guard"])
    guard_writer["evidence"].append({
        "source_url": "https://example.com/writer_ev",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": "2026-09-22T16:14:56Z",
        "evidence_sha": current_sha,
        "runtime_binding": current_runtime,
        "validity": "VALID",
        "reason": "writer",
        "producer_id": "PRODUCER-01",
        "verifier_id": "WRITER-01",
    })
    with pytest.raises(LedgerError) as exc:
        update(ledger, bundle["revision"], {"STATUS": "READY"}, "WRITER-01", 5.0, guard_writer)
    assert "decision path" in str(exc.value) or "caller-created" in str(exc.value)

    # Sub-case 5: Same-update evidence consumption cannot achieve acceptance
    guard_foreign = copy.deepcopy(bundle["acceptance_guard"])
    guard_foreign["evidence"].append({
        "source_url": "https://example.com/foreign_ev",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": "2026-09-22T16:14:56Z",
        "evidence_sha": current_sha,
        "runtime_binding": current_runtime,
        "validity": "VALID",
        "reason": "foreign",
        "producer_id": "INDEP-PRODUCER",
        "verifier_id": "INDEP-VERIFIER",
    })
    guard_foreign["transition_state"] = "CANONICAL_ACCEPTED"
    result = update(ledger, bundle["revision"], {"PROVEN_EDGES": ["issue state", "runtime artifact"], "UNPROVEN_EDGES": []}, "FOREIGN-WRITER", 5.0, guard_foreign)
    # Must remain PROVISIONAL in the same update where evidence is introduced!
    assert result["acceptance_guard"]["transition_state"] == "PROVISIONAL"
    assert result["record"]["CLEAN_IDLE"] != "YES"


def test_warhead_c_stale_sha(tmp_path):
    """WARHEAD C: STALE_SHA must fail closed."""
    ledger = tmp_path / "ledger_warhead_c.json"
    initialize(ledger)
    bundle = load_bundle(ledger)
    current_sha = bundle["record"]["CURRENT_SHA"]
    stale_sha = "f" * 40

    # Freshness check with different SHA must report STALE
    res = freshness(bundle, "release-candidate-integration", stale_sha, "NO_FURTHER_ACTION", [], bundle["record"]["RUNTIME_IDENTITY"])
    assert res["FRESHNESS"] == "STALE"
    assert "CURRENT_SHA_MISMATCH" in res["REASONS"]

    # Evidence with stale SHA marked VALID must raise LedgerError
    guard = copy.deepcopy(bundle["acceptance_guard"])
    guard["evidence"].append({
        "source_url": "https://example.com/stale_sha_ev",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": "2026-09-22T16:14:56Z",
        "evidence_sha": stale_sha,
        "runtime_binding": guard["binding"]["runtime_identity"],
        "validity": "VALID",
        "reason": "mismatched sha",
        "producer_id": "P-01",
        "verifier_id": "V-01",
    })
    with pytest.raises(LedgerError) as exc:
        update(ledger, bundle["revision"], {"STATUS": "READY"}, "V-01", 5.0, guard)
    assert "mismatched SHA/runtime binding" in str(exc.value)


def test_warhead_d_wrong_actual_runtime_sha(tmp_path):
    """WARHEAD D: WRONG_ACTUAL_RUNTIME_SHA must fail closed."""
    ledger = tmp_path / "ledger_warhead_d.json"
    initialize(ledger)
    bundle = load_bundle(ledger)
    current_sha = bundle["record"]["CURRENT_SHA"]

    # Freshness check with wrong runtime identity must report STALE
    res = freshness(bundle, "release-candidate-integration", current_sha, "NO_FURTHER_ACTION", [], "WRONG_RUNTIME_IDENTITY")
    assert res["FRESHNESS"] == "STALE"
    assert "RUNTIME_IDENTITY_MISMATCH" in res["REASONS"]

    # Evidence with mismatched runtime binding marked VALID must raise LedgerError
    guard = copy.deepcopy(bundle["acceptance_guard"])
    guard["evidence"].append({
        "source_url": "https://example.com/wrong_runtime_ev",
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": "2026-09-22T16:14:56Z",
        "evidence_sha": current_sha,
        "runtime_binding": "WRONG_RUNTIME_HOST",
        "validity": "VALID",
        "reason": "mismatched runtime",
        "producer_id": "P-01",
        "verifier_id": "V-01",
    })
    with pytest.raises(LedgerError) as exc:
        update(ledger, bundle["revision"], {"STATUS": "READY"}, "V-01", 5.0, guard)
    assert "mismatched SHA/runtime binding" in str(exc.value)


def test_warhead_e_empty_unproven_edges(tmp_path):
    """WARHEAD E: EMPTY_UNPROVEN_EDGES without physical evidence must fail closed."""
    ledger = tmp_path / "ledger_warhead_e.json"
    initialize(ledger)
    bundle = load_bundle(ledger)

    # Empty UNPROVEN_EDGES without physical proof in prior evidence
    updated = update(
        ledger,
        bundle["revision"],
        {"PROVEN_EDGES": ["issue state", "runtime artifact"], "UNPROVEN_EDGES": []},
        "V-01",
        5.0,
    )
    assert updated["acceptance_guard"]["transition_state"] == "PROVISIONAL"
    assert updated["record"]["CLEAN_IDLE"] == "NO"
    assert updated["record"]["QUEUE_INDEPENDENT"] == "NO"
    assert updated["record"]["STATUS"] == "WAITING_PHYSICAL_PROOF"

    # Attempting to directly force CLEAN_IDLE=YES when physical proof is absent must fail
    with pytest.raises(LedgerError) as exc:
        update(ledger, updated["revision"], {"CLEAN_IDLE": "YES"}, "V-01", 5.0)
    assert "CLEAN_IDLE=YES is forbidden" in str(exc.value)


def test_warhead_f_false_clean_idle(tmp_path):
    """WARHEAD F: FALSE_CLEAN_IDLE must fail closed."""
    ledger = tmp_path / "ledger_warhead_f.json"
    initialize(ledger)
    bundle = load_bundle(ledger)

    # 1. CLEAN_IDLE=YES with active NEXT_EXECUTABLE_ACTION is forbidden
    with pytest.raises(LedgerError) as exc:
        update(ledger, bundle["revision"], {"CLEAN_IDLE": "YES", "NEXT_EXECUTABLE_ACTION": "SOME_ACTION"}, "V-01", 5.0)
    assert "CLEAN_IDLE=YES is forbidden" in str(exc.value)

    # 2. CLEAN_IDLE=YES with UNPROVEN_EDGES non-empty is forbidden
    with pytest.raises(LedgerError) as exc:
        update(ledger, bundle["revision"], {"CLEAN_IDLE": "YES", "NEXT_EXECUTABLE_ACTION": "NONE", "UNPROVEN_EDGES": ["runtime artifact"]}, "V-01", 5.0)
    assert "CLEAN_IDLE=YES is forbidden" in str(exc.value)

    # 3. CLEAN_IDLE=YES when STATUS is READY/BLOCKED is forbidden
    with pytest.raises(LedgerError) as exc:
        update(ledger, bundle["revision"], {"CLEAN_IDLE": "YES", "NEXT_EXECUTABLE_ACTION": "NONE", "STATUS": "READY"}, "V-01", 5.0)
    assert "CLEAN_IDLE=YES is forbidden" in str(exc.value)
