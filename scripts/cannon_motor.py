#!/usr/bin/env python3
"""Cannon motor: serial single-worker Dauerlauf with Cannon control contract.

Reuses scripts/work_queue.py (read-only, via CLI subprocess) for queue truth.
Owns only its motor state file: <state_dir>/motor.json (atomic replace).

States: IDLE RUNNING PAUSED STOP_AFTER_CURRENT STOPPING COMPLETED ERROR
Controls: start / request_pause / request_resume / request_stop.
Reload: a new CannonMotor(state_dir) instance recovers backend truth.

Invariants: MAX_ACTIVE=1, no DONE restart, UNKNOWN halts the chain,
no human relay between normal tasks (human_continue stays 0).
"""
import hashlib
import itertools
import json
import os
import subprocess
import sys
import time
from pathlib import Path

STATES = ("IDLE", "RUNNING", "PAUSED", "STOP_AFTER_CURRENT",
          "STOPPING", "COMPLETED", "ERROR")
WORK_QUEUE = Path(__file__).resolve().parent / "work_queue.py"
WORKER_ID = "cannon-motor-1"


class MotorError(Exception):
    pass


def deterministic_executor(results_dir, task, behavior="ok"):
    """Local deterministic worker. No network, no provider, no LLM.

    Returns (outcome, result_id) where outcome is 'ok' or 'unknown'.
    Persists a result artifact for every ok execution.
    """
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    if behavior == "unknown":
        return ("unknown", None)
    task_id = task['task_id']
    if behavior == "crash":
        raise MotorError(f"executor crash on {task_id}")
    import hashlib
    identity = {
        'task_id': task_id,
        'attempt_id': task.get('attempt_id'),
        'dispatch_id': task.get('dispatch_id'),
        'executor_kind': 'LOCAL_FAKE'
    }
    payload_str = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    result_id = "result-" + hashlib.sha256(payload_str).hexdigest()
    artifact = results_dir / f"{task_id}.result.json"
    payload = {"result_id": result_id, "task_id": task_id,
               "outcome": "ok", "persisted_at": time.time()}
    tmp = artifact.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8")
    tmp.replace(artifact)
    return ("ok", result_id)


class CannonMotor:
    def __init__(self, state_dir, behaviors=None, hooks=None):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir = self.state_dir / "results"
        self.motor_file = self.state_dir / "motor.json"
        self.behaviors = behaviors or {}
        self.hooks = hooks or {}
        self._load()

    # ---- persistence: motor.json is the backend truth ----
    def _load(self):
        if self.motor_file.exists():
            self.m = json.loads(self.motor_file.read_text(encoding="utf-8"))
        else:
            self.m = {"run_id": None, "state": "IDLE",
                      "current_task": None, "pause_requested": False,
                      "stop_requested": False, "stop_count": 0,
                      "executions": {}, "needs_review": [],
                      "max_active_observed": 0, "human_continue": 0,
                      "error": None, "completed_runs": 0,
                      "run_mode": "FINITE", "start_limit": None,
                      "started_count": 0, "done_count": 0,
                      "cooldown_seconds": 5.0, "saved_prompt": None,
                      "executed_inputs": [], "last_result": None,
                      "waiting_for_work": False}
            self._save()
        self.yolo = None
        if os.environ.get("COURIER_CANNON_PROFILE") == "yolo":
            _p = str(Path(__file__).resolve().parent)
            if _p not in sys.path: sys.path.insert(0, _p)
            import cannon_yolo
            self.yolo = cannon_yolo.Yolo(self.m.setdefault("yolo", {}), save=self._save)

    def _save(self):
        tmp = self.motor_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.m, indent=1, sort_keys=True) + "\n",
                       encoding="utf-8")
        tmp.replace(self.motor_file)

    @property
    def state(self):
        return self.m["state"]

    # ---- work_queue.py CLI (reused, never modified) ----
    def _wq(self, *argv):
        out = subprocess.check_output(
            [sys.executable, str(WORK_QUEUE), "--state-dir",
             str(self.state_dir), *argv], text=True)
        return json.loads(out)

    def queue_snapshot(self):
        return self._wq("state")

    # ---- controls ----
    def start(self, mode=None, limit=None, cooldown=5.0, local_fake=False, continuous_canary=False):
        """mode: FINITE (BEGRENZT) drains queue or limit; INFINITE (UNENDLICH)
        idles when the queue is empty instead of completing. limit is only a
        persisted countdown — tasks are never pre-created. cooldown waits
        AFTER confirmed completion, never instead of it."""
        if self.m["state"] == "RUNNING":
            return {"started": False, "reason": "already_running",
                    "run_id": self.m["run_id"]}
        if self.m.get("needs_review") or self.m.get("current_task"):
            return {"started": False, "reason": "review_required"}
        if self.m["state"] not in ("IDLE", "COMPLETED", "ERROR", "PAUSED", "BLOCKED"):
            return {"started": False,
                    "reason": f"illegal_transition_from_{self.m['state']}"}
        effective_mode = mode or self.m.get("run_mode", "FINITE")
        if effective_mode not in ("FINITE", "INFINITE"):
            return {"started": False, "reason": "bad_mode"}
        if self.m["state"] != "PAUSED":
            self.m["run_id"] = f"run-{int(time.time() * 1000)}"
            self.m["pause_requested"] = False
            self.m["stop_requested"] = False
            self.m["stop_count"] = 0  # duplicate suppression belongs to this run
            self.m["error"] = None
            self.m["waiting_for_work"] = False
            self.m["run_mode"] = effective_mode
            self.m["local_fake"] = local_fake
            self.m["continuous_canary"] = continuous_canary
            if mode is not None or limit is not None:
                self.m["start_limit"] = None if effective_mode == "INFINITE" else limit
            self.m["cooldown_seconds"] = cooldown
            if effective_mode == "FINITE" and mode is not None:
                # Fresh finite run: per-run counters restart. Resume-from-PAUSED
                # keeps them; reopen-without-start never touches them.
                self.m["started_count"] = 0
                self.m["done_count"] = 0
        self.m["state"] = "RUNNING"
        self._save()
        return {"started": True, "run_id": self.m["run_id"],
                "mode": self.m["run_mode"], "limit": self.m["start_limit"]}

    def save_prompt(self, prompt_id, text, semantics="readonly"):
        """PROMPT_SOURCE=SAVED_SINGLE_PROMPT. semantics: readonly, idempotent
        or mutating. Mutating prompts may never repeat the same input."""
        if semantics not in ("readonly", "idempotent", "mutating"):
            return {"saved": False, "reason": "bad_semantics"}
        self.m["saved_prompt"] = {"prompt_id": prompt_id, "text": text,
                                  "semantics": semantics}
        self._save()
        return {"saved": True, "prompt_id": prompt_id,
                "semantics": semantics}

    @staticmethod
    def input_hash(prompt_id, description):
        return hashlib.sha1(
            f"{prompt_id}|{description}".encode("utf-8")).hexdigest()[:16]

    def request_pause(self):
        if self.m["state"] == "PAUSED":
            return {"paused": True, "reason": "already_paused"}
        self.m["pause_requested"] = True
        self._save()
        return {"paused": True, "reason": "pause_after_current"}

    def request_resume(self):
        if self.m["state"] == "RUNNING":
            return {"resumed": False, "reason": "already_running"}
        if self.m["state"] != "PAUSED":
            return {"resumed": False,
                    "reason": f"illegal_transition_from_{self.m['state']}"}
        self.m["pause_requested"] = False
        self.m["state"] = "RUNNING"
        self._save()
        return {"resumed": True, "run_id": self.m["run_id"]}

    def request_stop(self):
        self.m["stop_count"] += 1
        if self.m["stop_count"] > 1:
            self._save()
            return {"stopped": False, "reason": "already_requested"}
        self.m["stop_requested"] = True
        if self.m["state"] == "RUNNING":
            self.m["state"] = "STOP_AFTER_CURRENT"
        self._save()
        return {"stopped": True, "reason": "stop_after_current"}

    def _prompt_guard(self, task_id):
        """Refuse duplicate mutating-prompt inputs before execution.

        Returns a refusal report dict, or None when execution may proceed.
        Distinct task identity/input passes; readonly/idempotent passes."""
        sp = self.m.get("saved_prompt")
        if not sp:
            return None
        # Re-read the full task record for prompt binding (the state CLI
        # only returns statuses; this is a read-only look at backend truth).
        task = None
        try:
            raw = json.loads(
                (self.state_dir / "queue.json").read_text(encoding="utf-8"))
            task = raw.get("tasks", {}).get(task_id)
        except (OSError, ValueError):
            task = None
        prompt_id = (task or {}).get("prompt_id")
        if prompt_id != sp["prompt_id"]:
            return None  # task does not use the saved prompt
        if sp["semantics"] in ("readonly", "idempotent"):
            return None
        ihash = self.input_hash(prompt_id, (task or {}).get("description", ""))
        if ihash in self.m.get("executed_inputs", []):
            self._wq("block", task_id, "--reason",
                     "DUPLICATE_EFFECT_RISK")
            return {"step": "refused_duplicate_effect", "task": task_id,
                    "state": self.m["state"]}
        return None

    # ---- serial execution: exactly one task per step ----
    def remaining(self):
        if self.m["run_mode"] == "INFINITE":
            return None  # ∞
        if self.m["start_limit"] is not None:
            return max(self.m["start_limit"] - self.m["started_count"], 0)
        return None  # drain mode: derived from queue by the caller

    def _admit_next_task(self):
        """One explicit task, never a preallocated limit-sized list.

        Reuse the canonical queue. A previous admission must be durably DONE
        with its matching artifact before a new identity can be admitted.
        """
        snap = self.queue_snapshot()
        if any(t.get("status") in ("CLAIMED", "RUNNING", "VERIFYING")
               for t in snap["tasks"].values()):
            raise MotorError("unfinished_task_requires_review")
        if any(t.get("status") != "DONE" for t in snap["tasks"].values()):
            return  # existing work (including ambiguity) must not be replaced
        last = self.m.get("last_result")
        if self.m.get("started_count", 0):
            if not last or snap["tasks"].get(last["task"], {}).get("status") != "DONE":
                raise MotorError("previous_result_not_reconciled")
            artifact = self.results_dir / (last["task"] + ".result.json")
            receipt = json.loads(artifact.read_text(encoding="utf-8"))
            if (receipt.get("task_id") != last["task"]
                    or receipt.get("result_id") != last["result_id"]
                    or receipt.get("outcome") != "ok"):
                raise MotorError("previous_result_not_verified")
        if self.m.get("pause_requested") or self.m.get("stop_requested"):
            return
            
        is_fake = self.m.get("local_fake", False)
        prefix = "local-fake-" if is_fake else "real-canary-"
        package = prefix + self.m["run_id"]
        task_id = package + "-" + str(self.m["started_count"] + 1)
        self._wq("init", package)
        
        task_data = {
            "task_id": task_id, "package_id": package,
            "description": "Explicit local fake task (no model/provider)" if is_fake else "Explicit real muse canary task",
            "dependencies": [], "read_scopes": [],
            "write_scopes": ["cannon-local-fake"] if is_fake else ["cannon-real-canary"],
            "status": "READY"
        }
        if not is_fake:
            task_data["executor_kind"] = "REAL_MUSE"
            task_data["acceptance"] = "isolated_nonce_canary_v1"
            task_data["provider"] = "meta"
            
        self._wq("add", json.dumps(task_data))

    def run_step(self):
        """Execute at most one task. Returns a step report dict."""
        if self.m["state"] not in ("RUNNING", "STOP_AFTER_CURRENT"):
            return {"step": "noop", "state": self.m["state"]}
        if (self.m["run_mode"] == "FINITE"
                and self.m["start_limit"] is not None
                and self.m["started_count"] >= self.m["start_limit"]):
            self.m["state"] = "COMPLETED"
            self.m["current_task"] = None
            self.m["completed_runs"] += 1
            self._save()
            if getattr(self, "yolo", None) is not None: self.yolo.end("LIMIT_MOTOR")
            return {"step": "limit_reached", "state": "COMPLETED"}
        if self.m.get("local_fake") or self.m.get("continuous_canary"):
            # Persisted deadline also covers reopening during the cooldown.
            delay = self.m.get("next_admission_after", 0) - time.time()
            if delay > 0:
                time.sleep(delay)
                self._load()
            if self.m.get("pause_requested") or self.m.get("stop_requested"):
                self.m["state"] = "PAUSED" if self.m.get("pause_requested") else "IDLE"
                self._save()
                if getattr(self, "yolo", None) is not None: self.yolo.end("STOPP")
                return {"step": "controlled_stop", "state": self.state}
            try:
                self._admit_next_task()
            except (MotorError, OSError, ValueError) as exc:
                self.m["state"] = "ERROR"
                self.m["error"] = str(exc)
                self._save()
                return {"step": "error", "error": str(exc)}
        if getattr(self, "yolo", None) is not None:
            why = self.yolo.gate()
            if why:
                self.yolo.end(why)
                self.m["state"] = "IDLE"
                self.m["current_task"] = None
                self._save()
                return {"step": "yolo_end", "reason": why, "state": "IDLE"}
            try:
                _snap = self.queue_snapshot()
            except Exception:
                _snap = {"tasks": {}}
            _open = [t for t in _snap.get("tasks", {}).values() if t.get("status") in ("READY", "WAITING", "CLAIMED", "RUNNING", "VERIFYING")]
            if not _open:
                known = list(_snap.get("tasks", {}).keys())
                tid = self.yolo.next_task(known=known)
                if tid:
                    try:
                        self._wq("add", json.dumps({"task_id": tid, "package_id": "yolo-" + str(self.yolo.s.get("run", "run")), "description": "Repo-Aufgabe " + tid, "dependencies": [], "read_scopes": [], "write_scopes": [], "status": "READY"}))
                    except Exception as _e:
                        try:
                            self._wq("block", tid, "--reason", "BRAUCHT_PRUEFUNG")
                        except Exception:
                            pass
                        if tid not in self.m.get("needs_review", []):
                            self.m["needs_review"].append(tid)
                        self.m["state"] = "BLOCKED"
                        self.m["error"] = "unknown_effect:%s" % tid
                        self.m["current_task"] = None
                        self._save()
                        self.yolo.end("UNKNOWN add-fehlgeschlagen")
                        return {"step": "unknown_halt", "task": tid, "state": "BLOCKED"}
        claimed = self._wq("claim", "--worker", WORKER_ID)
        task_id = claimed.get("claimed")
        if not task_id:
            if self.m["run_mode"] == "INFINITE":
                # WARTET: no filler work, no busy loop, no model polling.
                self.m["state"] = "IDLE"
                self.m["current_task"] = None
                self.m["waiting_for_work"] = True
                self._save()
                if getattr(self, "yolo", None) is not None: self.yolo.end("LEERLAUF")
                return {"step": "waiting_for_work", "state": "IDLE"}
            self.m["state"] = "COMPLETED"
            self.m["current_task"] = None
            self.m["completed_runs"] += 1
            self._save()
            if getattr(self, "yolo", None) is not None: self.yolo.end("LEERLAUF")
            return {"step": "queue_empty", "state": "COMPLETED"}
        self.m["current_task"] = task_id
        self.m["max_active_observed"] = max(
            self.m["max_active_observed"], 1)
        self._save()
        # Saved-prompt guard: a mutating prompt may never repeat an input.
        refused = self._prompt_guard(task_id)
        if refused:
            self.m["current_task"] = None
            self._save()
            return refused
        self.m["started_count"] += 1
        self._save()
        hook = self.hooks.get("on_task_start")
        if hook:
            hook(self, task_id)
        if getattr(self, "yolo", None) is not None:
            try:
                kind, detail, res = self.yolo.execute(task_id)
            except Exception as _e:
                kind, detail, res = "unknown", "EXEC_FEHLER", None
            if kind == "done":
                self.m["executions"][task_id] = self.m["executions"].get(task_id, 0) + 1
                import hashlib
                _payload_str = json.dumps({'task_id': task_id, 'executor_kind': 'YOLO'}, sort_keys=True).encode()
                _rid = (res.get("commit") if isinstance(res, dict) else None) or ("result-" + hashlib.sha256(_payload_str).hexdigest())
                _artifact = self.results_dir / f"{task_id}.result.json"
                _payload = {"result_id": _rid, "task_id": task_id,
                            "outcome": "ok", "persisted_at": time.time(),
                            "yolo": res}
                try:
                    self.results_dir.mkdir(parents=True, exist_ok=True)
                    _tmp = _artifact.with_suffix(".tmp")
                    _tmp.write_text(json.dumps(_payload, indent=1, sort_keys=True) + "\n",
                                    encoding="utf-8")
                    _tmp.replace(_artifact)
                except (OSError, ValueError):
                    self._wq("block", task_id, "--reason", "BRAUCHT_PRUEFUNG")
                    if task_id not in self.m.get("needs_review", []):
                        self.m["needs_review"].append(task_id)
                    self.m["state"] = "BLOCKED"
                    self.m["error"] = f"unknown_effect:{task_id}"
                    self.m["current_task"] = None
                    self._save()
                    self.yolo.end("UNKNOWN BRAUCHT_PRUEFUNG")
                    return {"step": "unknown_halt", "task": task_id, "state": "BLOCKED"}
                completed = self._wq("complete", task_id, "--result-json", json.dumps({"result_id": _rid, "yolo": res}), "--stage", "ACCEPTED")
                if completed.get("done") != task_id or completed.get("stage") != "ACCEPTED":
                    self.m["state"] = "BLOCKED"
                    self.m["error"] = "result_not_reconciled"
                    self._save()
                    self.yolo.end("UNKNOWN result_not_reconciled")
                    return {"step": "error", "error": self.m["error"]}
                try:
                    _receipt = json.loads(_artifact.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    _receipt = {}
                if (_receipt.get("task_id") != task_id
                        or _receipt.get("result_id") != _rid
                        or _receipt.get("outcome") != "ok"):
                    self._wq("block", task_id, "--reason", "BRAUCHT_PRUEFUNG")
                    if task_id not in self.m.get("needs_review", []):
                        self.m["needs_review"].append(task_id)
                    self.m["state"] = "BLOCKED"
                    self.m["error"] = f"unknown_effect:{task_id}"
                    self.m["current_task"] = None
                    self._save()
                    self.yolo.end("UNKNOWN BRAUCHT_PRUEFUNG")
                    return {"step": "unknown_halt", "task": task_id, "state": "BLOCKED"}
                self.m["done_count"] += 1
                self.m["last_result"] = {"task": task_id, "result_id": _rid, "completed_at": time.time(), "yolo": res}
                try:
                    raw = json.loads((self.state_dir / "queue.json").read_text(encoding="utf-8"))
                    t = raw.get("tasks", {}).get(task_id, {})
                except (OSError, ValueError):
                    t = {}
                sp = self.m.get("saved_prompt")
                if sp and t.get("prompt_id") == sp["prompt_id"]:
                    ihash = self.input_hash(sp["prompt_id"], t.get("description", ""))
                    if ihash not in self.m["executed_inputs"]:
                        self.m["executed_inputs"].append(ihash)
                self.m["current_task"] = None
                self.m["next_admission_after"] = time.time() + (self.m.get("cooldown_seconds", 5.0) or 0)
                self._save()
                cooldown = self.m.get("cooldown_seconds", 5.0) or 0
                if cooldown > 0:
                    time.sleep(cooldown)
                    self._load()
                if self.m["pause_requested"]:
                    self.m["pause_requested"] = False
                    self.m["state"] = "PAUSED"
                    self._save()
                    self.yolo.end("STOPP")
                elif self.m["stop_requested"]:
                    snap = self.queue_snapshot()
                    remaining = [t for t, v in snap["tasks"].items() if v.get("status") in ("READY", "WAITING")]
                    self.m["state"] = "IDLE" if remaining else "COMPLETED"
                    if self.m["state"] == "COMPLETED":
                        self.m["completed_runs"] += 1
                    self._save()
                    self.yolo.end("STOPP")
                return {"step": "done", "task": task_id, "state": self.m["state"]}
            elif kind == "failed":
                self.m["executions"][task_id] = self.m["executions"].get(task_id, 0) + 1
                self._wq("block", task_id, "--reason", "YOLO_FEHLER")
                if task_id not in self.m.get("needs_review", []):
                    self.m["needs_review"].append(task_id)
                self.m["state"] = "BLOCKED"
                self.m["error"] = str(detail or "YOLO_FEHLER")
                import hashlib
                _payload_str = json.dumps({'task_id': task_id, 'executor_kind': 'YOLO'}, sort_keys=True).encode()
                _rid = "result-" + hashlib.sha256(_payload_str).hexdigest()
                self.m["last_result"] = {"task": task_id, "result_id": _rid, "completed_at": time.time(), "yolo": res}
                self.m["current_task"] = None
                self._save()
                self.yolo.end("FEHLER " + str(detail or ""))
                return {"step": "error", "task": task_id, "error": self.m["error"]}
            else:
                self.m["executions"][task_id] = self.m["executions"].get(task_id, 0) + 1
                self._wq("block", task_id, "--reason", "BRAUCHT_PRUEFUNG")
                if task_id not in self.m.get("needs_review", []):
                    self.m["needs_review"].append(task_id)
                self.m["state"] = "BLOCKED"
                self.m["error"] = f"unknown_effect:{task_id}"
                self.m["current_task"] = None
                self._save()
                self.yolo.end("UNKNOWN " + str(detail or ""))
                return {"step": "unknown_halt", "task": task_id, "state": "BLOCKED"}
        behavior = self.behaviors.get(task_id, "ok")
        try:
            # The display snapshot deliberately omits executor metadata.
            # Select from the authoritative claimed record, never that projection.
            task = json.loads((self.state_dir / 'queue.json').read_text())['tasks'][task_id]
            kind = task.get('executor_kind', 'LOCAL_FAKE')
            if kind == 'LOCAL_FAKE':
                outcome, result_id = deterministic_executor(self.results_dir, task, behavior)
            elif kind == 'REAL_MUSE':
                from app.cannon.adapters import LiveMuseAdapter
                def persist_identity(identity):
                    self.m['active_execution'] = identity
                    self._save()
                outcome, result_id = LiveMuseAdapter.execute_canary(task, self.results_dir, persist_identity)
            else:
                raise MotorError('UNKNOWN_EXECUTOR_KIND')
        except (MotorError, ValueError, OSError) as exc:
            self._wq('block', task_id, '--reason', 'REAL_EXECUTION_REQUIRES_REVIEW')
            self.m['needs_review'].append(task_id)
            self.m["state"] = "BLOCKED"
            self.m["error"] = str(exc)
            self.m["current_task"] = None
            self._save()
            if getattr(self, "yolo", None) is not None: self.yolo.end("FEHLER " + str(exc))
            return {"step": "error", "task": task_id,
                    "error": str(exc)}
        self.m["executions"][task_id] = \
            self.m["executions"].get(task_id, 0) + 1
        if outcome == "unknown":
            self._wq("block", task_id, "--reason", "BRAUCHT_PRUEFUNG")
            self.m["needs_review"].append(task_id)
            self.m["state"] = "BLOCKED"
            self.m["error"] = f"unknown_effect:{task_id}"
            self.m["current_task"] = None
            self._save()
            if getattr(self, "yolo", None) is not None: self.yolo.end("UNKNOWN BRAUCHT_PRUEFUNG")
            return {"step": "unknown_halt", "task": task_id,
                    "state": "BLOCKED"}
        completed = self._wq("complete", task_id, "--result-json",
                 json.dumps({"result_id": result_id}),
                 "--stage", "ACCEPTED")
        if completed.get("done") != task_id or completed.get("stage") != "ACCEPTED":
            self.m["state"] = "BLOCKED"
            self.m["error"] = "result_not_reconciled"
            self._save()
            return {"step": "error", "error": self.m["error"]}
        self.m["done_count"] += 1
        self.m["last_result"] = {"task": task_id, "result_id": result_id,
                                 "completed_at": time.time()}
        try:
            raw = json.loads(
                (self.state_dir / "queue.json").read_text(encoding="utf-8"))
            t = raw.get("tasks", {}).get(task_id, {})
        except (OSError, ValueError):
            t = {}
        sp = self.m.get("saved_prompt")
        if sp and t.get("prompt_id") == sp["prompt_id"]:
            ihash = self.input_hash(sp["prompt_id"],
                                    t.get("description", ""))
            if ihash not in self.m["executed_inputs"]:
                self.m["executed_inputs"].append(ihash)
        self.m["current_task"] = None
        self.m["next_admission_after"] = time.time() + (self.m.get("cooldown_seconds", 5.0) or 0)
        self._save()
        # Cooldown AFTER confirmed completion — never instead of it.
        cooldown = self.m.get("cooldown_seconds", 5.0) or 0
        if cooldown > 0:
            time.sleep(cooldown)
            self._load()  # include controls persisted by the web process
        # Control flags take effect between tasks, never mid-task.
        if self.m["pause_requested"]:
            self.m["pause_requested"] = False
            self.m["state"] = "PAUSED"
            if getattr(self, "yolo", None) is not None: self.yolo.end("STOPP")
        elif self.m["stop_requested"]:
            snap = self.queue_snapshot()
            remaining = [t for t, v in snap["tasks"].items()
                         if v.get("status") in ("READY", "WAITING")]
            self.m["state"] = "IDLE" if remaining else "COMPLETED"
            if self.m["state"] == "COMPLETED":
                self.m["completed_runs"] += 1
            if getattr(self, "yolo", None) is not None: self.yolo.end("STOPP")
        self._save()
        return {"step": "done", "task": task_id,
                "state": self.m["state"]}

    def run(self, max_steps=1000):
        """Dauerlauf: repeat run_step until the run leaves RUNNING."""
        reports = []
        for _ in range(max_steps):
            if self.m["state"] not in ("RUNNING", "STOP_AFTER_CURRENT"):
                break
            reports.append(self.run_step())
        return reports

    def supervise(self, max_cycles=1000, idle_sleep=1.0):
        """Bounded overnight supervisor. Starts the persisted run when IDLE,
        steps while RUNNING, and waits with a bounded sleep when the infinite
        run idles on an empty queue. Never busy-loops, never invents work."""
        for _ in (range(max_cycles) if max_cycles is not None else itertools.count()):
            self._load()
            if self.m.get("waiting_for_work") or self.m.get("stop_requested"):
                break  # WARTET: no authorized work; exit, do not poll/restart
            if self.m["state"] not in ("RUNNING", "STOP_AFTER_CURRENT"):
                break
            self.run_step()
        return {"state": self.m["state"],
                "started": self.m["started_count"],
                "done": self.m["done_count"],
                "remaining": self.remaining()}

    # ---- acceptance counters ----
    def invariants(self):
        execs = self.m["executions"]
        Artifacts = list(self.results_dir.glob("*.result.json")) \
            if self.results_dir.exists() else []
        done_with_artifact = 0
        snap = self.queue_snapshot()
        for tid, info in snap["tasks"].items():
            if info.get("status") == "DONE":
                if (self.results_dir / f"{tid}.result.json").exists():
                    done_with_artifact += 1
        duplicates = sum(c - 1 for c in execs.values() if c > 1)
        lost = len(execs) - done_with_artifact - len(self.m["needs_review"])
        return {"DUPLICATE_EXECUTIONS": duplicates,
                "LOST_RESULTS": max(lost, 0),
                "MAX_ACTIVE": self.m["max_active_observed"],
                "HUMAN_CONTINUE": self.m["human_continue"],
                "DONE": sum(1 for v in snap["tasks"].values()
                            if v.get("status") == "DONE"),
                "STARTED": self.m["started_count"],
                "DONE_COUNT": self.m["done_count"],
                "REMAINING": self.remaining(),
                "RUN_MODE": self.m.get("run_mode", "FINITE")}
