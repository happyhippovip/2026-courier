import json
import time
import os
import subprocess
import threading
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass

@dataclass
class CriticalSnapshot:
    provider: str
    host: str
    session_id: str
    workkey: str
    process_identity: str
    current_state: str
    last_useful_progress: float
    current_sha: str
    checkpoint_reference: str
    writer_ownership: str
    pending_action: str

class KirbySupervisor:
    """Kirby supervision contract: continuous watch over provider session."""
    def __init__(self, provider: str, host: str, session_id: str, state_dir: str):
        self.provider = provider
        self.host = host
        self.session_id = session_id
        self.state_dir = state_dir
        self.last_useful_progress = time.time()
        self.last_snapshot = time.time()
        self.current_workkey = None
        self._stop_event = threading.Event()
        self._thread = None

    def start(self, get_state_cb: Callable[[], Dict[str, Any]]):
        self._get_state = get_state_cb
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join()

    def _watch_loop(self):
        while not self._stop_event.is_set():
            now = time.time()
            state = self._get_state()
            # Fast fallback heartbeat
            self._check_health(state)
            
            # 15min Critical snapshot
            if now - self.last_snapshot > 15 * 60:
                self._take_snapshot(state)
                self.last_snapshot = now
            
            self._stop_event.wait(30.0)

    def _check_health(self, state: Dict[str, Any]):
        """Lightweight health/progress heartbeat."""
        pass # To be implemented based on provider logs/telemetry

    def _take_snapshot(self, state: Dict[str, Any]):
        """Forensic/recovery evidence."""
        snap = CriticalSnapshot(
            provider=self.provider,
            host=self.host,
            session_id=self.session_id,
            workkey=state.get("workkey", ""),
            process_identity=state.get("process_identity", ""),
            current_state=state.get("state", "UNKNOWN"),
            last_useful_progress=self.last_useful_progress,
            current_sha=self._get_git_sha(),
            checkpoint_reference=state.get("checkpoint", ""),
            writer_ownership=state.get("writer_ownership", ""),
            pending_action=state.get("pending_action", "")
        )
        path = os.path.join(self.state_dir, f"snapshot_{self.session_id}.json")
        with open(path, "w") as f:
            json.dump(snap.__dict__, f)

    def _get_git_sha(self):
        try:
            return subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
        except Exception:
            return ""

    def on_turn_end(self, workkey: str, state: str):
        """Primary detection: provider turn-end / idle event."""
        # 1. Read latest durable checkpoint
        # 2. Re-fetch current repo/master state
        # 3. Classify current workkey: COMPLETE / BLOCKED / STILL_OPEN
        # 4. Reconcile writer ownership
        # 5. If useful authorized work remains, emit exactly ONE continuation wake
        pass


class WakeCoalescer:
    """Ensures exactly 0 or 1 pending continuation wakes exist per session."""
    def __init__(self):
        self._pending_wake = False
        self._lock = threading.Lock()
        
    def request_wake(self) -> bool:
        """Returns True if a wake was actually queued, False if coalesced."""
        with self._lock:
            if self._pending_wake:
                return False
            self._pending_wake = True
            return True
            
    def consume_wake(self) -> bool:
        """Consumes the pending wake if one exists."""
        with self._lock:
            if self._pending_wake:
                self._pending_wake = False
                return True
            return False

class SessionRotator:
    """Context-aware rotation."""
    def __init__(self):
        pass
        
    def prepare_rotation(self, session_id: str, checkpoint: str):
        """1. Finish/checkpoint the smallest safe atomic step.
           2. Stop accepting new workkeys.
           3. Persist workkey, SHA, evidence, continuation point.
           4. Release mutable ownership safely.
           5. Start/reuse exactly ONE fresh replacement session."""
        pass
