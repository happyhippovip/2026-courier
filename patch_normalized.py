with open("scripts/courier_founder_mode.py", "r") as f:
    text = f.read()

text = text.replace(
"""        elif task_type == "IMPLEMENTATION":
            files = last_result.get("changed_files", [])
            return [{
                "goal": goal_text,
                "normalized_task": f"Verify implementation in {', '.join(files)}",
                "capability_required": "repo verification",
                "preferred_agent": "CLI1",
                "is_heavy": False,
                "requires_write": False,
                "is_heavy": True,""",
"""        elif task_type == "IMPLEMENTATION":
            files = last_result.get("changed_files", [])
            files_str = ", ".join(files) if len(files) <= 5 else f"{len(files)} files"
            return [{
                "goal": goal_text,
                "normalized_task": f"Verify implementation in {files_str}",
                "capability_required": "repo verification",
                "preferred_agent": "CLI1",
                "is_heavy": False,
                "requires_write": False,
                "is_heavy": True,"""
)

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(text)
