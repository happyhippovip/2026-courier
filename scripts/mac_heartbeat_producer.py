import json
import time
import os
import uuid
import datetime
import signal
import sys
from pathlib import Path

HEARTBEAT_PATH = Path("coordination/heartbeats/mac_heartbeat.json")
NODE_ID = "MAC_CHIEF_01"
PLATFORM = "MAC"
PROCESS_ID = str(uuid.uuid4())
RUNNING = True

def handle_sigint(sig, frame):
    global RUNNING
    print("Shutting down heartbeat producer...")
    RUNNING = False

signal.signal(signal.SIGINT, handle_sigint)
signal.signal(signal.SIGTERM, handle_sigint)

def atomic_write(filepath: Path, data: dict):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = filepath.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, filepath)

def run_heartbeat():
    state_gen = 0
    print(f"Starting Mac Heartbeat Producer (Process {PROCESS_ID})")
    
    while RUNNING:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        heartbeat = {
            "node_id": NODE_ID,
            "host": PLATFORM,
            "timestamp_utc": now,
            "state_generation": state_gen,
            "process_instance_id": PROCESS_ID,
            "active_request_id": None,
            "writer_state": "IDLE",
            "lease_epoch": 1,
            "last_verified_result": None
        }
        
        try:
            atomic_write(HEARTBEAT_PATH, heartbeat)
            state_gen += 1
        except Exception as e:
            print(f"Error writing heartbeat: {e}")
            
        time.sleep(15)

if __name__ == "__main__":
    run_heartbeat()
    # Clean shutdown: perhaps remove heartbeat or mark offline? The prompt doesn't specify removing it, but TTL handles it.
    print("Heartbeat stopped.")
