import os
import sys
import time

def verify_state_isolation(state_dir="server/state", max_age_seconds=3600):
    errors = []
    
    if not os.path.exists(state_dir):
        os.makedirs(state_dir, exist_ok=True)
        
    for item in os.listdir(state_dir):
        path = os.path.join(state_dir, item)
        if os.path.isfile(path):
            age = time.time() - os.path.getmtime(path)
            if age > max_age_seconds:
                errors.append(f"Stale state file detected: {item} (Age: {age}s). Isolation failure or missed cleanup.")
                
    if not errors:
        print("STATE ISOLATION VALID")
        sys.exit(0)
    else:
        print("STATE ISOLATION FAILED:")
        for err in errors:
            print(f" - {err}")
        sys.exit(1)

if __name__ == "__main__":
    verify_state_isolation()
