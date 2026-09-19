import json

transcript_path = "/Users/user/.gemini/antigravity/brain/c61b931a-e4f1-476d-b9d2-431218079df5/.system_generated/logs/transcript_full.jsonl"
patches = []
with open(transcript_path, "r") as f:
    for line in f:
        try:
            data = json.loads(line)
        except:
            continue
        
        if data.get("type") == "PLANNER_RESPONSE":
            for call in data.get("tool_calls", []):
                if call.get("name") in ("default_api:replace_file_content", "default_api:write_to_file"):
                    args = call.get("arguments", {})
                    target = args.get("TargetFile", "")
                    if "agent_handoff_ledger.py" in target:
                        patches.append(args)

with open("recover_patches.json", "w") as f:
    json.dump(patches, f, indent=2)
print(f"Total patches: {len(patches)}")
