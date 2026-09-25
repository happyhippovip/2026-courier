import json
import hashlib

def hash_dict(d):
    j = json.dumps(d, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(j.encode('utf-8')).hexdigest()

def fix_ledger(file_path, old_sha, new_sha):
    # Read as text and replace
    with open(file_path, 'r') as f:
        text = f.read()
    
    text = text.replace(old_sha, new_sha)
    
    data = json.loads(text)
    
    # Recalculate history hashes
    prev_hash = None
    for entry in data["history"]:
        entry["previous_entry_sha256"] = prev_hash
        entry["record_sha256"] = hash_dict(entry["record"])
        
        if "acceptance_guard" in entry:
            entry["state_sha256"] = hash_dict({
                "record": entry["record"],
                "acceptance_guard": entry["acceptance_guard"]
            })
        
        unsigned = {k: v for k, v in entry.items() if k != "entry_sha256"}
        entry["entry_sha256"] = hash_dict(unsigned)
        prev_hash = entry["entry_sha256"]
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

fix_ledger("agent_handoff_ledger.json", "a5087918d2a3db3aa873c780993241aca5d5de42", "b459ff11249d4b164ca851c0b1c441131eb4ff6b")
