import json
import re
with open(r"C:\Users\lol\.gemini\antigravity\brain\ec711710-4565-4f5b-9ad4-8d95cd8540b9\.system_generated\logs\transcript_full.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        try:
            d = json.loads(line)
            c = d.get("content", "")
            match = re.search(r"(W13[^\n]+(?:\n[^\n]+){1,3})", c)
            if match and "BOUNDED" in match.group(1):
                print(match.group(1))
                break
        except Exception as e:
            pass

