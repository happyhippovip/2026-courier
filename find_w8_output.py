import json
with open(r"C:\Users\lol\.gemini\antigravity\brain\ec711710-4565-4f5b-9ad4-8d95cd8540b9\.system_generated\logs\transcript_full.jsonl", "r", encoding="utf-8") as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if "cat issue37.txt | Select-String" in line and "Context 0,5" in line:
            print("Found command at step index in array", i)
            # print the next few steps
            for j in range(1, 5):
                if i+j < len(lines):
                    print("--- Next step:")
                    d = json.loads(lines[i+j])
                    if d.get("type") == "GENERIC":
                        print(d.get("content"))

