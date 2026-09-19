import json
import glob

chunk_files = sorted(glob.glob("/Users/user/.gemini/antigravity/brain/c61b931a-e4f1-476d-b9d2-431218079df5/.system_generated/logs/chunks/transcript_full/*.jsonl"))
patches = []
for fpath in chunk_files:
    with open(fpath, "r", errors="ignore") as f:
        for line in f:
            try:
                data = json.loads(line)
            except:
                continue
            if data.get("type") == "PLANNER_RESPONSE":
                for call in data.get("tool_calls", []):
                    if call.get("name") in ("default_api:replace_file_content", "default_api:write_to_file", "default_api:run_command"):
                        args = call.get("arguments", {})
                        target = args.get("TargetFile", "")
                        cmd = args.get("CommandLine", "")
                        if "agent_handoff_ledger.py" in target:
                            patches.append(args)

with open("recover_patches.json", "w") as f:
    json.dump(patches, f, indent=2)
print(f"Total found: {len(patches)}")
