import json
import os
COURIER_DIR = "."
with open("ops/ai/wall_ledger/ledger.jsonl") as f:
    for line in f:
        data = json.loads(line)
        ev_path = data.get("EVIDENCE_PATH")
        if not ev_path or not os.path.exists(ev_path) or os.path.isdir(ev_path): continue
        file_fp = None
        legacy_fp = None
        with open(ev_path, 'r', errors='ignore') as ef:
            for eline in ef:
                if "DO_NOT_REPEAT_FINGERPRINT=" in eline:
                    file_fp = eline.split("DO_NOT_REPEAT_FINGERPRINT=")[1].strip()
                elif "DO_NOT_REPEAT:" in eline:
                    legacy_fp = eline.split("DO_NOT_REPEAT:")[1].strip()
        final_fp = file_fp if file_fp else legacy_fp
        ledger_fp = data.get("FINGERPRINT")
        if final_fp != ledger_fp:
            print(f"{data['TASK_ID']}: Ledger={ledger_fp}, File={final_fp}")
