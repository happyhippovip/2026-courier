import time
import json
import os

from server import ledger

print("Testing ACTION_LEDGER...")
ledger.record_action(
    goal_id="g123",
    task_id="t123",
    request_id="req123",
    worker="w123",
    action_type="DISPATCHED",
    input_scope="unrestricted",
    output_ref=None,
    status="DISPATCHED",
    next_action="EXECUTE",
    human_req=False,
    canonical_ref="ref123"
)

print("Testing RESULT_PROVENANCE_LEDGER...")
ledger.record_result(
    task_id="t123",
    request_id="req123",
    worker="w123",
    result_id="res123",
    changed_files=["minimal_proof.txt"],
    fingerprint_val="hash123",
    customs_status="PASS",
    verifier="v123",
    accepted=True,
    rejection_reason=None,
    next_ready_task=None,
    duplicate_effect=False
)

print("Testing COST_USAGE_LEDGER...")
ledger.record_cost(
    provider="test_provider",
    account="test_account",
    model="test_model",
    task_id="t123",
    start_time=time.time(),
    end_time=time.time()+10,
    requests=1,
    input_tokens=100,
    output_tokens=50,
    credits_consumed=1,
    eur_usd_cost=0.01,
    rate_limit_event=False,
    fallback_provider=None,
    est_human_work_saved="ESTIMATE:10min"
)

print("Testing HUMAN_GATE_LEDGER...")
ledger.record_human_gate(
    goal_task="t123",
    category="PERMISSION",
    requested_decision="approve_write",
    why_automation_stopped="requires root",
    safe_to_continue=False,
    status="pending",
    approver_ref=None
)

print("Testing VALUE_REVENUE_LEDGER...")
ledger.record_value(
    goal_task="g123",
    asset_created="new_feature",
    customer_relevance="high",
    confirmed_revenue="UNKNOWN",
    confirmed_mrr="UNKNOWN",
    confirmed_cost_reduction="UNKNOWN",
    estimated_opportunity="ESTIMATE:1000",
    target_contribution="EUR_239_MONTH",
    evidence="user feedback",
    status="VERIFIED"
)

print("Testing RETRY_DUPLICATE_LEDGER...")
ledger.record_retry(
    original_task="t123",
    retry_reason="timeout",
    previous_result=None,
    idempotency_key="idempotent123",
    effect_exists=False,
    retry_executed=True,
    duplicate_prevented=False
)

print("Proof complete.")
