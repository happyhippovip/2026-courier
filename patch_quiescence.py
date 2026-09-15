import sys

with open('scripts/run_live_production_goal.py', 'r') as f:
    code = f.read()

old_eval = """                    "payload": {
                        "action": "evaluate_goal_completion",
                        "prompt": "The immediate opportunity queue is empty. Is the overall goal fully demonstrably complete? Goal: " + goal + " If not complete, identify the next safe concrete dependency/task and output it.",
                        "allowed_scope": ["SAFE_LOCAL_VALIDATION"]
                    }"""

new_eval = """                    "payload": {
                        "action": "evaluate_goal_completion",
                        "prompt": f"The opportunity queue currently has {len(queue.list_opportunities())} tasks. Are there any pending blocked tasks? If so, identify an entirely different disjoint task (e.g. Windows) to make progress. Goal: {goal}. Is the overall goal fully demonstrably complete? If not complete, identify the next safe concrete dependency/task and output it.",
                        "allowed_scope": ["SAFE_LOCAL_VALIDATION"]
                    }"""

code = code.replace(old_eval, new_eval)

with open('scripts/run_live_production_goal.py', 'w') as f:
    f.write(code)
