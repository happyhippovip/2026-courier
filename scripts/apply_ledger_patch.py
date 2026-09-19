import re

with open("server/app.py", "r") as f:
    code = f.read()

# 1. Patch set_task_status
set_status_hook = """
    try:
        import server.ledger as ledger
        if new_status in ("DISPATCHED", "QUEUED", "RESULT_RECEIVED", "RECONCILED", "FAILED_TERMINAL", "AWAIT_MERGE_APPROVAL", "WAITING_PROVIDER", "HUMAN_REQUIRED"):
            ledger.record_action(
                goal_id=task.get("goal_id"),
                task_id=task.get("task_id"),
                request_id=task.get("dispatch_id") or task.get("attempt_id"),
                worker=task.get("worker_id"),
                action_type=new_status,
                input_scope=task.get("merge_scope"),
                output_ref=task.get("result", {}).get("result_id") if isinstance(task.get("result"), dict) else None,
                status=new_status,
                next_action=task.get("next_action"),
                human_req=task.get("human_intervention_required", False),
                canonical_ref=task.get("execution_ref")
            )
        if new_status == "HUMAN_REQUIRED":
            ledger.record_human_gate(
                goal_task=task.get("task_id"),
                category="OTHER", 
                requested_decision="approve_execution",
                why_automation_stopped=task.get("blocker"),
                safe_to_continue=False,
                status="pending",
                approver_ref=None
            )
    except Exception:
        pass
"""
code = code.replace('    task["status"] = new_status\n', '    task["status"] = new_status\n' + set_status_hook)

# 2. Patch task_result duplicate
task_res_dup = """
            if is_identical:
                try:
                    import server.ledger as ledger
                    ledger.record_retry(task.get("task_id"), "duplicate_result", existing_result.get("result_id"), None, True, False, True)
                except Exception:
                    pass
                return jsonify({"status": "ACK_DUPLICATE"})
"""
code = code.replace("""            if is_identical:\n                return jsonify({"status": "ACK_DUPLICATE"})\n""", task_res_dup)

# 3. Patch task_result cost
task_res_cost = """
            try:
                import server.ledger as ledger
                ledger.record_cost(
                    provider=task.get("worker_provider", "unknown"),
                    account="unknown",
                    model="unknown",
                    task_id=task.get("task_id"),
                    start_time=task.get("dispatched_at", time.time()),
                    end_time=time.time(),
                    requests=1,
                    input_tokens="UNKNOWN",
                    output_tokens="UNKNOWN",
                    credits_consumed="UNKNOWN",
                    eur_usd_cost="UNKNOWN",
                    rate_limit_event=False,
                    fallback_provider="unknown",
                    est_human_work_saved="ESTIMATE"
                )
            except Exception:
                pass
"""
code = code.replace('            task["result_received_at"] = time.time()\n', '            task["result_received_at"] = time.time()\n' + task_res_cost)

# 4. Patch verify_task_result
verify_res = """
    try:
        import server.ledger as ledger
        # Assuming fingerprint is imported in app.py (it is: from scripts.attestation_contract import fingerprint)
        fprint = fingerprint(result) if result else None
        ledger.record_result(
            task_id=task.get("task_id"),
            request_id=task.get("dispatch_id"),
            worker=task.get("worker_id"),
            result_id=result.get("result_id") if result else None,
            changed_files=result.get("artifacts") if result else None,
            fingerprint_val=fprint,
            customs_status="PASS" if verdict == "PASS" else "FAIL",
            verifier=verifier_id,
            accepted=True if verdict == "PASS" else False,
            rejection_reason=data.get("reason") if verdict == "FAIL" else None,
            next_ready_task=None,
            duplicate_effect=False
        )
    except Exception as e:
        print(f"ledger error: {e}")
"""
code = code.replace('    if verdict not in {"PASS", "FAIL"}:\n', verify_res + '\n    if verdict not in {"PASS", "FAIL"}:\n')

# 5. Patch verify_task_result goal done
goal_done = """
                    goal["status"] = "DONE"
                    try:
                        import server.ledger as ledger
                        ledger.record_value(
                            goal_task=goal.get("goal_id"),
                            asset_created="goal_completion",
                            customer_relevance="UNKNOWN",
                            confirmed_revenue="UNKNOWN",
                            confirmed_mrr="UNKNOWN",
                            confirmed_cost_reduction="UNKNOWN",
                            estimated_opportunity="ESTIMATE:UNKNOWN",
                            target_contribution="EUR_239_MONTH",
                            evidence="goal_done",
                            status="BUILT"
                        )
                    except Exception:
                        pass
"""
code = code.replace('                    goal["status"] = "DONE"\n', goal_done)

with open("server/app.py", "w") as f:
    f.write(code)

print("Patch applied.")
