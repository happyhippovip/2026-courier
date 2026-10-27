"""P2 R2 test helper: a real in-process controller journal with verified RESULT_ACCEPTED events."""
import hashlib
import types

from courier_core.controller import Controller
from courier_core.events import EventType
from courier_core.verification import Verdict

FORGED = ("journal:1:RESULT_ACCEPTED", "journal:999999:RESULT_ACCEPTED|sha256:" + "0" * 64,
          "local-verified:sha256:" + "a" * 64)   # P0 probe of review R1: none of them may be DONE


class View(types.SimpleNamespace):  # test double: View(_journal=j, method=...) = j with some methods replaced
    def __getattr__(self, name):
        return getattr(self._journal, name)


class JournalHome:  # accept(): one task through create/claim/start/result/verify, real journal
    def __init__(self, tmp_path, nested=True):
        self.home, self.count, self.ctrl = tmp_path / "ctrl_home" if nested else tmp_path, 0, None
        self.restart()

    def restart(self):  # stop the controller (stop() closes its journal), boot a new one on the same courier.db
        if self.ctrl is not None:
            self.ctrl.stop()
        self.ctrl = Controller(self.home, verifier=lambda adapter: (lambda task, result, h: Verdict(True, "test")),
                               clock=lambda: 1000.0).boot()
        self.journal = self.ctrl.journal
        return self.journal

    def accept(self, workkey, key=None, payload=b"P2R2", results=None):  # results: ids per attempt, last succeeds
        self.count += 1
        results = results or [f"r-{self.count}"]
        created = self.ctrl.create_task({"adapter": "synthetic", "params": {"estimated_cost_eur": 0.0},
                                         "effect_class": "idempotent", "max_attempts": len(results), "lease_ttl_s": 10,
                                         "idempotency_key": key or f"workkey:{workkey}"})
        task_id = self.task_id = created[1]["task_id"]
        self.digests = []
        for attempt, rid in enumerate(results, 1):
            c = self.ctrl.claim({"worker_id": "w1"})
            self.ctrl.start({"dispatch_id": c["dispatch_id"], "worker_id": "w1"})
            name, data = f"out{self.count}-{attempt}.bin", payload + f"{workkey}#{self.count}-{attempt}".encode()
            (self.home / name).write_bytes(data)
            self.digests.append(hashlib.sha256(data).hexdigest())
            self.ctrl.result({"dispatch_id": c["dispatch_id"], "result_id": rid, "retryable": True,
                              "outcome": "success" if attempt == len(results) else "failure",
                              "artifacts": [{"path": name, "sha256": self.digests[-1]}]})
            self.ctrl.drain()
        (seq,) = [e.seq for e in self.journal.events(task_id=task_id) if e.type is EventType.RESULT_ACCEPTED]
        return f"journal:{seq}:RESULT_ACCEPTED|sha256:{self.digests[-1]}"
