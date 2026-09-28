import sys

def main():
    with open("server/app.py", "r") as f:
        content = f.read()

    new_content = content.replace("""        for step in goal["workflow_plan"]:
            step["goal_id"] = goal_id
            step["status"] = "QUEUED"
            step["attempts"] = 0""", """        for step in goal["workflow_plan"]:
            target_agent = str(step.get("target_agent", "linux")).lower()
            if "github" in target_agent: target_agent = "github"
            elif "windows" in target_agent or "codex" in target_agent: target_agent = "windows"
            elif "mac" in target_agent or "antigravity" in target_agent or "gemini" in target_agent: target_agent = "mac"
            else: target_agent = "linux"
            step["target_agent"] = target_agent
            step["goal_id"] = goal_id
            step["status"] = "QUEUED"
            step["attempts"] = 0""")

    with open("server/app.py", "w") as f:
        f.write(new_content)

if __name__ == "__main__":
    main()
