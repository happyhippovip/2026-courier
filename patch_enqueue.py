import sys

with open("scripts/run_live_production_goal.py", "r") as f:
    code = f.read()

old_block = """                    try:
                        res = adapters["GEMINI"](task_envelope)
                        print(f"GEMINI Goal Evaluation Result: {res}")
                        # We just let it run. If it outputs a plan-disc or plan-imp task, it should be in the queue?
                        # Wait, evaluate_goal_completion doesn't enqueue! It returns a payload.
                        # Wait, what does evaluate_goal_completion do in courier_real_worker_adapters?
                    except Exception as e:
                        print(f"Goal evaluation failed: {e}")"""

new_block = """                    try:
                        res = adapters["GEMINI"](task_envelope)
                        print(f"GEMINI Goal Evaluation Result: {res}")
                        if res and "result" in res:
                            payload = res["result"].get("payload", {})
                            summary = payload.get("summary", "")
                            if summary and summary != "GOAL_IS_COMPLETE_YES":
                                import uuid
                                from scripts.opportunity_queue import Opportunity
                                task_id_new = f"plan-imp-{uuid.uuid4().hex[:8]}"
                                opp = Opportunity(
                                    opportunity_id=task_id_new,
                                    source="MAC_CHIEF",
                                    project="Courier",
                                    description=summary,
                                    priority=5,
                                    risk="LOW",
                                    target_agent="CODEX",
                                    allowed_actions=["implement_bounded_improvement"],
                                    allowed_scope=["GLOBAL"]
                                )
                                queue.add_opportunity(opp)
                                queue.save_opportunity(opp)
                                print(f"Enqueued new task from Gemini: {task_id_new}")
                    except Exception as e:
                        print(f"Goal evaluation failed: {e}")"""

code = code.replace(old_block, new_block)

with open("scripts/run_live_production_goal.py", "w") as f:
    f.write(code)
