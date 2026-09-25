import os
import sys
import time
import json
from pathlib import Path

def set_console_title(title):
    if os.name == 'nt':
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    else:
        sys.stdout.write(f"\033]0;{title}\007")
        sys.stdout.flush()

def resolve_state_file(slot_id):
    """Canonical repo-root state first; legacy wall-dir state as fallback."""
    wall_dir = Path(__file__).resolve().parent
    canonical = wall_dir.parent.parent / "runtime" / "slots" / slot_id / "state.json"
    if canonical.exists():
        return canonical
    return wall_dir / "runtime" / "slots" / slot_id / "state.json"


def main():
    if len(sys.argv) < 2:
        print("Usage: watcher.py <slot_id>")
        sys.exit(1)

    slot_id = sys.argv[1]
    last_state = None
    
    print(f"Monitoring {slot_id}...")
    
    while True:
        try:
            state_file = resolve_state_file(slot_id)
            if state_file.exists():
                with open(state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    state = data.get("state", "UNKNOWN")
            else:
                state = "OFFLINE"
                
            if state != last_state:
                set_console_title(f"{slot_id} | {state}")
                print(f"[{time.strftime('%H:%M:%S')}] State changed to {state}")
                last_state = state
                
        except Exception as e:
            pass
            
        time.sleep(1)

if __name__ == "__main__":
    main()
