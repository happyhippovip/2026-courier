#!/usr/bin/env python3
import json
import os
import zipfile
import datetime
import subprocess

def get_system_health():
    return {
        "os": os.name,
        "disk_free_gb": getattr(os.statvfs('.'), 'f_bavail', 0) * getattr(os.statvfs('.'), 'f_frsize', 0) / (1024**3) if hasattr(os, 'statvfs') else "N/A"
    }

def create_support_bundle():
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    bundle_name = f"support_bundle_{timestamp}.zip"
    
    with zipfile.ZipFile(bundle_name, 'w') as zf:
        # Include health info
        health_info = get_system_health()
        zf.writestr('health.json', json.dumps(health_info, indent=2))
        
        # Include redacted state (just queue sizes, statuses, NO secrets/CoT)
        state_file = 'central_state.json'
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                try:
                    state = json.load(f)
                    redacted_state = {
                        "queue_summary": {
                            "total_goals": len(state.get("goals", {})),
                            "total_tasks": len(state.get("tasks", {}))
                        }
                    }
                    zf.writestr('queue_summary.json', json.dumps(redacted_state, indent=2))
                except Exception as e:
                    zf.writestr('queue_summary.json', json.dumps({"error": str(e)}))
                    
        # Include version info (assuming version.txt exists or via git)
        try:
            git_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('utf-8').strip()
            zf.writestr('version.txt', f"git_hash: {git_hash}\n")
        except Exception:
            zf.writestr('version.txt', "version: unknown\n")
            
    print(f"Support bundle created: {bundle_name}")

if __name__ == "__main__":
    create_support_bundle()
