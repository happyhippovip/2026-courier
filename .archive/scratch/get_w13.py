import json
with open(r"C:\Users\lol\.gemini\antigravity\brain\ec711710-4565-4f5b-9ad4-8d95cd8540b9\.system_generated\logs\transcript_full.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        try:
            d = json.loads(line)
            c = d.get("content", "")
            if c and "W13" in c and "issue37.txt" in c:
                print("====================================")
                print(c)
        except Exception as e:
            pass

