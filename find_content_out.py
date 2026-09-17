import json
with open(r"C:\Users\lol\.gemini\antigravity\brain\ec711710-4565-4f5b-9ad4-8d95cd8540b9\.system_generated\logs\transcript_full.jsonl", "r", encoding="utf-8") as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if "Select-Object -Skip 920" in line or "Select-Object -Skip 930" in line:
            print(f"Found command at step {i}")
            for j in range(1, 5):
                if i+j < len(lines):
                    d = json.loads(lines[i+j])
                    if d.get("type") == "GENERIC":
                        print("OUTPUT:", d.get("content"))
                        break

