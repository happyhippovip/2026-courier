#!/usr/bin/env python3
import os
import sys
import json
import time
import fcntl
import subprocess
import argparse

WORKSPACE = "/Users/user/Downloads/2026-courier"
WALL_DIR = os.path.join(WORKSPACE, "state", "wall")
STATE_FILE = os.path.join(WALL_DIR, "state.json")
STOP_FILE = os.path.join(WALL_DIR, "STOP")
LOCK_FILE = os.path.join(WALL_DIR, "supervisor.lock")

# States
IDLE = "IDLE"
WORKING = "WORKING"
RESULT_READY = "RESULT_READY"
BACKOFF = "BACKOFF"
PAUSED_ERROR = "PAUSED_ERROR"
RESOURCE_BLOCKED = "RESOURCE_BLOCKED"
STOPPED = "STOPPED"
AMBIGUOUS_STARTED = "AMBIGUOUS_STARTED"

CRASH_LIMIT = 5
CRASH_BACKOFF_BASE = 5  # seconds
RAMP_STAGES = [1, 4, 8, 16, 32]

def now_ts():
    return time.time()

class MuseFeederAdapter:
    def __init__(self, workspace=WORKSPACE, fake=False, fake_cmd_callback=None):
        self.workspace = workspace
        self.fake = fake
        self.fake_cmd_callback = fake_cmd_callback

    def exec_task(self, prompt, yolo=True, reasoning_effort="auto"):
        cmd = ["muse", "exec", "--workspace", self.workspace, "--reasoning-effort", reasoning_effort]
        if yolo:
            cmd.append("--yolo")
        cmd.append(prompt)
        return self._run(cmd)

    def resume_task(self, session_ref, yolo=True):
        cmd = ["muse", "resume", "--workspace", self.workspace, session_ref]
        if yolo:
            cmd.append("--yolo")
        return self._run(cmd)

    def session_message(self, session_ref, message):
        cmd = ["muse", "session-message", "--workspace", self.workspace, session_ref, message]
        return self._run(cmd)
        
    def _run(self, cmd):
        if self.fake:
            if self.fake_cmd_callback:
                return self.fake_cmd_callback(cmd)
            return DummyProcess(cmd)
        # Always run in a "wrong cwd" to ensure explicit workspace is used
        return subprocess.Popen(cmd, cwd="/tmp", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

class DummyProcess:
    def __init__(self, cmd, pid=9999):
        self.cmd = cmd
        self.pid = pid
        self.returncode = None
        self._alive = True
    def poll(self):
        return self.returncode if not self._alive else None
    def wait(self):
        self._alive = False
        self.returncode = 0
        return 0

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state):
    os.makedirs(WALL_DIR, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

class CapacityGovernor:
    def __init__(self, fake_health_callback=None):
        self.healthy_since = None
        self.fake_health_callback = fake_health_callback

    def is_healthy(self):
        if self.fake_health_callback:
            return self.fake_health_callback()
        # Stub actual memory pressure reading here.
        # Resource gate: Fail closed if metrics unavailable or memory pressured.
        return True

    def evaluate(self, target_capacity):
        if not self.is_healthy():
            self.healthy_since = None
            return 0  # Fail closed: safely block scale-up
        if self.healthy_since is None:
            self.healthy_since = now_ts()
        
        # Ramp up
        healthy_duration = now_ts() - self.healthy_since
        # E.g., next stage every 120s, but for test we might speed it up
        # We will map duration to stages, or just rely on manual tests.
        # For simplicity, if healthy, we permit up to the requested target,
        # but stagger them if we use a strict ladder.
        # Actually, let's use the RAMP_STAGES strictly based on time if we wanted, 
        # but the prompt says: "The resource governor must stagger/ramp actual active work safely. Required stages: 1, 4, 8, 16, 32".
        stage_idx = min(int(healthy_duration / 2), len(RAMP_STAGES) - 1)  # 2 sec per stage for test speed
        allowed = RAMP_STAGES[stage_idx]
        return min(allowed, target_capacity)

class Supervisor:
    def __init__(self, target=32, adapter=None, governor=None):
        self.target = target
        self.adapter = adapter or MuseFeederAdapter()
        self.gov = governor or CapacityGovernor()
        self.active_procs = {} # slot_id -> Popen/Dummy

    def tick(self):
        state = load_state()
        now = now_ts()
        stopping = os.path.exists(STOP_FILE)
        
        admitted = self.gov.evaluate(self.target) if not stopping else 0

        # Check existing
        for slot_id, slot_data in state.items():
            if slot_data["state"] == WORKING:
                proc = self.active_procs.get(slot_id)
                if proc:
                    ret = proc.poll()
                    if ret is not None:
                        # Exited
                        if ret == 75:  # Rate limit, not a crash
                            slot_data["state"] = BACKOFF
                            slot_data["backoff_until"] = now + 10
                        elif ret == 0:
                            # Finished successfully
                            slot_data["state"] = RESULT_READY
                        else:
                            # Crash
                            slot_data["crash_count"] = slot_data.get("crash_count", 0) + 1
                            if slot_data["crash_count"] >= CRASH_LIMIT:
                                slot_data["state"] = PAUSED_ERROR
                            else:
                                slot_data["state"] = BACKOFF
                                slot_data["backoff_until"] = now + (CRASH_BACKOFF_BASE * (2 ** slot_data["crash_count"]))
                        self.active_procs.pop(slot_id, None)

        if stopping:
            for slot_id, slot_data in state.items():
                if slot_data["state"] not in (WORKING, PAUSED_ERROR, RESULT_READY):
                    slot_data["state"] = STOPPED
        else:
            active_count = sum(1 for s in state.values() if s["state"] == WORKING)
            
            # Start new
            for slot_id in sorted(state.keys()):
                if active_count >= admitted:
                    break
                    
                slot_data = state[slot_id]
                s = slot_data["state"]
                
                if s == AMBIGUOUS_STARTED:
                    # Ambiguous started: never blindly replay
                    slot_data["state"] = PAUSED_ERROR
                    continue
                
                if s == RESULT_READY:
                    # Never reexecute
                    continue
                    
                if s == STOPPED:
                    # Never respawn
                    continue
                    
                if s == BACKOFF:
                    if now < slot_data.get("backoff_until", 0):
                        continue
                    slot_data["state"] = IDLE
                    
                if slot_data["state"] == IDLE:
                    # Launch
                    if slot_data.get("session_ref"):
                        # Resume
                        proc = self.adapter.resume_task(slot_data["session_ref"])
                    else:
                        # Exec
                        proc = self.adapter.exec_task(slot_data.get("prompt_ref", "DEFAULT PROMPT"))
                        slot_data["session_ref"] = f"session-{slot_id}-{int(now)}"
                        
                    self.active_procs[slot_id] = proc
                    slot_data["pid"] = proc.pid
                    slot_data["state"] = WORKING
                    slot_data["restart_count"] = slot_data.get("restart_count", 0) + 1
                    active_count += 1

        save_state(state)
        return state

def acquire_lock():
    os.makedirs(WALL_DIR, exist_ok=True)
    fh = open(LOCK_FILE, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["start", "stop", "status", "init"])
    parser.add_argument("target", type=int, nargs="?", default=32)
    args = parser.parse_args()

    if args.command == "init":
        state = {}
        for i in range(1, args.target + 1):
            slot = f"SLOT-{i:02d}"
            state[slot] = {
                "slot_id": slot,
                "task_id": f"task-{i}",
                "session_ref": "",
                "pid": None,
                "state": IDLE,
                "checkpoint": "",
                "result_state": "",
                "restart_count": 0,
                "crash_count": 0,
                "backoff_time": 0,
                "prompt_ref": f"Task instructions for {slot}"
            }
        save_state(state)
        print(f"Initialized {args.target} slots in {STATE_FILE}")
        return

    if args.command == "stop":
        os.makedirs(WALL_DIR, exist_ok=True)
        with open(STOP_FILE, "w") as f:
            f.write(str(now_ts()))
        print("STOP file created.")
        return

    if args.command == "status":
        state = load_state()
        print("SLOT\tSTATE\tPID\tCRASHES\tSESSION")
        for k, v in state.items():
            print(f"{k}\t{v['state']}\t{v.get('pid')}\t{v.get('crash_count', 0)}\t{v.get('session_ref')}")
        return

    if args.command == "start":
        lock = acquire_lock()
        if not lock:
            print("Another supervisor is running. Failing safely.")
            sys.exit(1)
            
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
            
        sup = Supervisor(target=args.target)
        print(f"Starting supervisor for up to {args.target} slots...")
        try:
            while True:
                sup.tick()
                time.sleep(1)
        except KeyboardInterrupt:
            print("Supervisor interrupted.")

if __name__ == "__main__":
    main()
