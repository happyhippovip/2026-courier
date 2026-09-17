import json
with open(r"C:\Users\lol\.gemini\antigravity\brain\ec711710-4565-4f5b-9ad4-8d95cd8540b9\.system_generated\logs\transcript_full.jsonl", "r", encoding="utf-8") as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        try:
            d = json.loads(line)
            c = d.get("content", "")
            if "W13 - BOUNDED AUTO-REPLENISH" in c and "W14" in c:
                print("====================================")
                print(c)
                break
        except Exception as e:
            pass

