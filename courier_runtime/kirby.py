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

    def on_turn_end(
        self,
        workkey: str,
        state: str,
        receipt: Optional[Any] = None,
        owned_identities: Optional[set] = None,
        accepted_log: Optional[Any] = None,
        step: Optional[int] = None,
        statement: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Primary detection: provider turn-end / idle event with receipt validation and continuation logging."""
        self.last_useful_progress = time.time()
        self.current_workkey = workkey

        # 1. Receipt validation if a receipt is provided
        validated_receipt_id = None
        if receipt is not None:
            from courier_runtime.receipt import validate as validate_receipt
            validate_receipt(receipt, owned_identities or set())
            validated_receipt_id = getattr(receipt, "receipt_id", str(time.time()))
            os.makedirs(self.state_dir, exist_ok=True)
            receipt_path = os.path.join(self.state_dir, f"receipt_{validated_receipt_id}.json")
            with open(receipt_path, "w") as f:
                if hasattr(receipt, "to_json"):
                    f.write(receipt.to_json())
                else:
                    json.dump(receipt, f)

        # 2. Durable ledger checkpointing
        status = "COMPLETED" if state in ("COMPLETE", "COMPLETED", "SUCCESS") else state
        summary = {
            "workkey": workkey,
            "session_id": self.session_id,
            "provider": self.provider,
            "host": self.host,
            "state": status,
            "receipt_id": validated_receipt_id,
            "timestamp": self.last_useful_progress,
        }

        # 3. Verified continuation logging
        if accepted_log is not None and status == "COMPLETED" and validated_receipt_id is not None and step is not None:
            from dataclasses import asdict
            from courier_runtime.continuation import AcceptedFact
            fact = AcceptedFact(
                workkey=workkey,
                step=step,
                statement=statement or f"step {step} completed and verified",
                sources=(f"receipt:{validated_receipt_id}",),
                accepted_by="controller",
                accepted_at=self.last_useful_progress,
            )
            accepted_log.append(fact)
            summary["accepted_fact"] = asdict(fact)

        os.makedirs(self.state_dir, exist_ok=True)
        summary_path = os.path.join(self.state_dir, f"ledger_summary_{self.session_id}.json")
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        return summary

    def decide_continuation(
        self,
        checkpoint: Any,
        grants_valid: Optional[Dict[str, bool]] = None,
        owned_alive: Optional[list] = None,
        lease_available: bool = True,
    ) -> Dict[str, Any]:
        """Evaluates verified continuation for the supervised session."""
        from courier_runtime.continuation import decide
        return decide(
            checkpoint,
            grants_valid=grants_valid if grants_valid is not None else {},
            owned_alive=owned_alive if owned_alive is not None else [],
            lease_available=lease_available,
        )


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
