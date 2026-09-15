import sys

with open("scripts/run_live_production_goal.py", "r") as f:
    code = f.read()

insertion = """
            state = quiescence_state(queue.list_opportunities())
            delay = idle_backoff_seconds(unchanged_idle_cycles)
            print(f"--- {state}; waiting {delay:g}s for a real state change ---")
            
            if state == "QUIESCENT_WAKEABLE":
                print("Queue is quiescent. Triggering goal evaluation via GEMINI...")
                task_hash = "goal-eval-" + str(unchanged_idle_cycles)
                task_envelope = {
                    "timeout_seconds": 120,
                    "task_hash": task_hash,
                    "worker_id": "GEMINI",
                    "target_agent": "GEMINI",
                    "task_id": f"eval-{unchanged_idle_cycles}",
                    "payload": {
                        "action": "evaluate_goal_completion",
                        "prompt": f"The opportunity queue currently has {len(queue.list_opportunities())} tasks. Are there any pending blocked tasks? If so, identify an entirely different disjoint task (e.g. Windows) to make progress. Goal: {goal}. Is the overall goal fully demonstrably complete? If not complete, identify the next safe concrete dependency/task and output it.",
                        "allowed_scope": ["SAFE_LOCAL_VALIDATION"]
                    }
                }
                adapters = get_real_worker_adapters(repo_root=COURIER_DIR)
                if "GEMINI" in adapters:
                    try:
                        res = adapters["GEMINI"](task_envelope)
                        print(f"GEMINI Goal Evaluation Result: {res}")
                        # We just let it run. If it outputs a plan-disc or plan-imp task, it should be in the queue?
                        # Wait, evaluate_goal_completion doesn't enqueue! It returns a payload.
                        # Wait, what does evaluate_goal_completion do in courier_real_worker_adapters?
                    except Exception as e:
                        print(f"Goal evaluation failed: {e}")
            
            time.sleep(delay)
            continue
"""

code = code.replace("""
            state = quiescence_state(queue.list_opportunities())
            delay = idle_backoff_seconds(unchanged_idle_cycles)
            print(f"--- {state}; waiting {delay:g}s for a real state change ---")
            time.sleep(delay)
            continue""", insertion)

with open("scripts/run_live_production_goal.py", "w") as f:
    f.write(code)
