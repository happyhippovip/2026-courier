"""P2 R2 test helper: a real in-process controller journal with verified RESULT_ACCEPTED events."""
import hashlib

from courier_core.controller import Controller
from courier_core.events import EventType
from courier_core.verification import Verdict

FORGED = ("journal:1:RESULT_ACCEPTED", "journal:999999:RESULT_ACCEPTED|sha256:" + "0" * 64,
          "local-verified:sha256:" + "a" * 64)   # P0 probe of review R1: none of them may be DONE


class JournalHome:  # accept(): one task through create/claim/start/result/verify, real journal
    def __init__(self, tmp_path, nested=True):
        self.home = tmp_path / "ctrl_home" if nested else tmp_path
        self.ctrl = Controller(self.home, verifier=lambda adapter: (lambda task, result, h: Verdict(True, "test")),
                               clock=lambda: 1000.0).boot()
        self.journal = self.ctrl.journal
        self.count = 0

    def accept(self, workkey, key=None, payload=b"P2R2"):
        """Proof of a new accepted task (idempotency key default workkey:<workkey>), built from the journal."""
        self.count += 1
        created = self.ctrl.create_task({"adapter": "synthetic", "params": {"estimated_cost_eur": 0.0},
                                         "effect_class": "idempotent", "max_attempts": 1, "lease_ttl_s": 10,
                                         "idempotency_key": key or f"workkey:{workkey}"})
        task_id = self.task_id = created[1]["task_id"]
        c = self.ctrl.claim({"worker_id": "w1"})
        self.ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "w1"})
        name, data = f"out{self.count}.bin", payload + f"{workkey}#{self.count}".encode()
        (self.home / name).write_bytes(data)
        self.ctrl.result({"dispatch_id": c["dispatch_id"], "result_id": f"r-{self.count}", "outcome": "success",
                          "artifacts": [{"path": name, "sha256": hashlib.sha256(data).hexdigest()}]})
        self.ctrl.drain()
        seq = [e.seq for e in self.journal.events(task_id=task_id) if e.type is EventType.RESULT_ACCEPTED]
        assert len(seq) == 1, (task_id, seq)
        return f"journal:{seq[0]}:RESULT_ACCEPTED|sha256:{hashlib.sha256(data).hexdigest()}"
