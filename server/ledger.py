import json
import os
import time

LEDGER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "events", "ledgers")

def _append(ledger_name, data):
    try:
        os.makedirs(LEDGER_DIR, exist_ok=True)
        path = os.path.join(LEDGER_DIR, f"{ledger_name}.jsonl")
        with open(path, "a") as f:
            f.write(json.dumps(data) + "\n")
    except Exception:
        pass

def record_action(goal_id, task_id, request_id, worker, action_type, input_scope, output_ref, status, next_action, human_req, canonical_ref):
    _append("action_ledger", {
        "timestamp": time.time(),
        "goal_id": goal_id,
        "task_id": task_id,
        "request_id": request_id,
        "worker": worker,
        "action_type": action_type,
        "input_scope": input_scope,
        "output_ref": output_ref,
        "status": status,
        "next_action": next_action,
        "human_intervention_required": human_req,
        "canonical_lineage_reference": canonical_ref
    })

def record_result(task_id, request_id, worker, result_id, changed_files, fingerprint_val, customs_status, verifier, accepted, rejection_reason, next_ready_task, duplicate_effect):
    _append("result_provenance_ledger", {
        "timestamp": time.time(),
        "task_id": task_id,
        "request_id": request_id,
        "worker": worker,
        "result_id": result_id,
        "changed_files": changed_files,
        "fingerprint": fingerprint_val,
        "result_customs_status": customs_status,
        "verifier": verifier,
        "accepted": accepted,
        "rejection_reason": rejection_reason,
        "next_ready_task": next_ready_task,
        "duplicate_effect_detected": duplicate_effect
    })

def record_cost(provider, account, model, task_id, start_time, end_time, requests, input_tokens, output_tokens, credits_consumed, eur_usd_cost, rate_limit_event, fallback_provider, est_human_work_saved):
    _append("cost_usage_ledger", {
        "timestamp": time.time(),
        "provider": provider,
        "account_pool": account,
        "model": model,
        "task_id": task_id,
        "start_time": start_time,
        "end_time": end_time,
        "requests": requests,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "credits_consumed": credits_consumed,
        "eur_usd_cost": eur_usd_cost,
        "rate_limit_event": rate_limit_event,
        "fallback_provider_used": fallback_provider,
        "estimated_human_work_saved": est_human_work_saved
    })

def record_human_gate(goal_task, category, requested_decision, why_automation_stopped, safe_to_continue, status, approver_ref):
    _append("human_gate_ledger", {
        "timestamp": time.time(),
        "goal_task": goal_task,
        "category": category,
        "requested_decision": requested_decision,
        "why_automation_stopped": why_automation_stopped,
        "safe_to_continue": safe_to_continue,
        "status": status,
        "approving_human_reference": approver_ref
    })

def record_value(goal_task, asset_created, customer_relevance, confirmed_revenue, confirmed_mrr, confirmed_cost_reduction, estimated_opportunity, target_contribution, evidence, status):
    _append("value_revenue_ledger", {
        "timestamp": time.time(),
        "goal_task": goal_task,
        "asset_created": asset_created,
        "customer_relevance": customer_relevance,
        "confirmed_revenue": confirmed_revenue,
        "confirmed_recurring_revenue": confirmed_mrr,
        "confirmed_cost_reduction": confirmed_cost_reduction,
        "estimated_opportunity_value": estimated_opportunity,
        "target_contribution": target_contribution,
        "evidence": evidence,
        "status": status
    })

def record_retry(original_task, retry_reason, previous_result, idempotency_key, effect_exists, retry_executed, duplicate_prevented):
    _append("retry_duplicate_ledger", {
        "timestamp": time.time(),
        "original_task": original_task,
        "retry_reason": retry_reason,
        "previous_result": previous_result,
        "idempotency_key": idempotency_key,
        "effect_already_exists": effect_exists,
        "retry_executed": retry_executed,
        "duplicate_prevented": duplicate_prevented
    })
