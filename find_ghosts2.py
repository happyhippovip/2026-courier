import json

transcript_path = "/Users/user/.gemini/antigravity/brain/c61b931a-e4f1-476d-b9d2-431218079df5/.system_generated/logs/transcript.jsonl"
tasks = {}

with open(transcript_path) as f:
    for line in f:
        try:
            entry = json.loads(line)
        except:
            continue
            
        if entry.get("status") == "RUNNING" and entry.get("type") == "GENERIC":
            content = entry.get("content", "")
            if "task id:" in content:
                parts = content.split("task id: ")
                if len(parts) > 1:
                    tid = parts[1].split("\n")[0].strip()
                    desc = ""
                    if "Task Description: " in content:
                        desc = content.split("Task Description: ")[1].split("\n")[0].strip()
                    if not desc.startswith("Timer:") and not desc.startswith("Cron:"):
                        tasks[tid] = {"started": True, "completed": False, "desc": desc, "created": entry.get("created_at")}
                    
        if entry.get("type") == "SYSTEM_MESSAGE":
            content = entry.get("content", "")
            for tid in list(tasks.keys()):
                if tid in content and ("finished with result" in content or "was canceled" in content):
                    tasks[tid]["completed"] = True

running_tasks = [(t, v) for t, v in tasks.items() if not v["completed"]]
running_tasks.sort(key=lambda x: x[1]["created"], reverse=True)

print(f"Non-scheduled ghost tasks running: {len(running_tasks)}")
for t, v in running_tasks:
    print(t, v["created"], v["desc"])
