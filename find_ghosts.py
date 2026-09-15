import json
import sys

transcript_path = "/Users/user/.gemini/antigravity/brain/c61b931a-e4f1-476d-b9d2-431218079df5/.system_generated/logs/transcript.jsonl"

tasks = {}
with open(transcript_path) as f:
    for line in f:
        try:
            entry = json.loads(line)
        except:
            continue
        
        # When a command runs async, it gets a task ID
        if "tool_calls" in entry:
            pass # We don't have task IDs in tool_calls usually, they come in the response
        
        if entry.get("type") == "TOOL_RESPONSE" and "content" in entry:
            content = entry["content"]
            if "Tool is running as a background task with task id:" in content:
                # Extract task ID
                parts = content.split("task id: ")
                if len(parts) > 1:
                    task_id = parts[1].split("\n")[0].strip()
                    tasks[task_id] = {"started": True, "completed": False}

        if entry.get("type") == "SYSTEM_MESSAGE":
            content = entry.get("content", "")
            if "finished with result" in content or "was canceled" in content:
                for tid in tasks.keys():
                    if tid in content:
                        tasks[tid]["completed"] = True

running_tasks = [t for t, v in tasks.items() if not v["completed"]]
print(f"Total started tasks: {len(tasks)}")
print(f"Ghost tasks running: {len(running_tasks)}")
for t in running_tasks:
    print(t)
