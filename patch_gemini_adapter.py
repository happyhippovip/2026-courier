import sys

with open('scripts/courier_real_worker_adapters.py', 'r') as f:
    code = f.read()

old_block = """        elif action == "discover_improvement_opportunities":
            goal_context = payload_in.get("goal_context", "")
            prompt = (
                f"{identity_headers}"
                "You are performing a read-only discovery task.\\n"
                f"GOAL CONTEXT: {goal_context}\\n"
                "Analyze the repository based on the goal context provided above. "
                "If the goal is already fully satisfied by the current repository state and no coherent gap exists, set 'weakness_id' to 'NONE'. Otherwise, provide a specific weakness_id.\\n"
                "Return ONLY a valid JSON object with exact keys: "
                "'correlation_id', 'mission_id', 'task_id', 'task_hash', 'target_agent', 'weakness_id', 'description', 'suggested_files' (list of strings), 'verification_strategy', "
                "'verdict' ('PASS' or 'HUMAN_APPROVAL_REQUIRED'), and 'summary'."
            )
            stage = "REAL_INDEPENDENT_DISCOVERY"
            task_type = "DISCOVERY"
        else:"""

new_block = """        elif action == "discover_improvement_opportunities":
            goal_context = payload_in.get("goal_context", "")
            prompt = (
                f"{identity_headers}"
                "You are performing a read-only discovery task.\\n"
                f"GOAL CONTEXT: {goal_context}\\n"
                "Analyze the repository based on the goal context provided above. "
                "If the goal is already fully satisfied by the current repository state and no coherent gap exists, set 'weakness_id' to 'NONE'. Otherwise, provide a specific weakness_id.\\n"
                "Return ONLY a valid JSON object with exact keys: "
                "'correlation_id', 'mission_id', 'task_id', 'task_hash', 'target_agent', 'weakness_id', 'description', 'suggested_files' (list of strings), 'verification_strategy', "
                "'verdict' ('PASS' or 'HUMAN_APPROVAL_REQUIRED'), and 'summary'."
            )
            stage = "REAL_INDEPENDENT_DISCOVERY"
            task_type = "DISCOVERY"
        elif action == "evaluate_goal_completion":
            prompt = (
                f"{identity_headers}"
                f"You are the autonomous orchestrator goal planner. {payload_in.get('prompt')}\\n"
                "Return ONLY a valid JSON object with exact keys: "
                "'correlation_id', 'mission_id', 'task_id', 'task_hash', 'target_agent', 'verdict' ('PASS' or 'HUMAN_APPROVAL_REQUIRED'), and 'summary' (the next concrete task description, OR 'GOAL_IS_COMPLETE_YES')."
            )
            stage = "REAL_INDEPENDENT_PLANNING"
            task_type = "PLANNING"
        else:"""

code = code.replace(old_block, new_block)

with open('scripts/courier_real_worker_adapters.py', 'w') as f:
    f.write(code)
