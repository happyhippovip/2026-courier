import sys
import json
import os
import hashlib
from pathlib import Path
import sqlite3

def main():
    try:
        input_data = json.load(sys.stdin)
    except:
        input_data = {}

    script_dir = Path(__file__).parent.resolve()
    repo_root = Path(os.environ.get("COURIER_REPO_ROOT", script_dir.parent))
    db_path = repo_root / ".courier_state" / "motor.db"
    
    if not db_path.exists():
        print(json.dumps({"decision": "stop", "reason": f"No motor.db found at {db_path}"}))
        return

    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        c = conn.cursor()
        
        # Check active conflicting writer by looking for a lock file (e.g. .courier_writer.lock)
        writer_lock = repo_root / ".courier_state" / ".courier_writer.lock"
        if writer_lock.exists():
            print(json.dumps({"decision": "stop", "reason": "ACTIVE_WRITER lock detected."}))
            return

        c.execute('''
            SELECT t.task_id 
            FROM tasks t
            WHERE t.status='PENDING' 
            AND t.gate_id IS NULL
            ORDER BY t.priority DESC, t.rowid ASC
            LIMIT 1
        ''')
        row = c.fetchone()
        
        if row:
            next_task = row[0]
            
            history_file = repo_root / ".courier_state" / "hook_history.json"
            history = []
            if history_file.exists():
                try:
                    with open(history_file, "r") as f:
                        history = json.load(f)
                except:
                    pass
                    
            if history.count(next_task) >= 3:
                print(json.dumps({"decision": "stop", "reason": f"Loop detected: Task {next_task} repeated 3 times without completion."}))
                return
                
            history.append(next_task)
            if len(history) > 10:
                history = history[-10:]
            with open(history_file, "w") as f:
                json.dump(history, f)
                
            print(json.dumps({
                "decision": "continue",
                "reason": f"Autonomous continuation: {next_task}"
            }))
            return
            
        print(json.dumps({"decision": "stop", "reason": "No safe pending tasks found. TRUE IDLE."}))
    except Exception as e:
        print(json.dumps({"decision": "stop", "reason": f"Error: {e}"}))
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
