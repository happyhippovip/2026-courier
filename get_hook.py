import json

with open("/Users/user/.gemini/antigravity/brain/c61b931a-e4f1-476d-b9d2-431218079df5/.system_generated/logs/transcript_full.jsonl") as f:
    for line in f:
        obj = json.loads(line)
        if obj.get("type") == "PLANNER_RESPONSE":
            for call in obj.get("tool_calls", []):
                if call["name"] == "replace_file_content":
                    args = call.get("args", {})
                    if "mac_result_consumer.py" in args.get("TargetFile", ""):
                        print("==== FOUND MODIFICATION ====")
                        print("StartLine:", args.get("StartLine"))
                        print("EndLine:", args.get("EndLine"))
                        print(args.get("ReplacementContent"))
                        print("============================")
