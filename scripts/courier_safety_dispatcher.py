"""Fail-closed local Courier dispatcher (no cloud invocation)."""
from __future__ import annotations

import hashlib, json, math, os, time, uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from scripts.resource_policy import TaskLeaseManager
from scripts.review_budget import ReviewLedger


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def canonical_task_hash(task_spec: dict[str, Any]) -> str:
    """Task identity excludes routing metadata, so routing never alters dedupe truth."""
    value = dict(task_spec)
    value.pop("capability_request", None)
    return canonical_hash(value)


def write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.flush(); os.fsync(handle.fileno())
    os.replace(tmp, path)


@dataclass(frozen=True)
class TaskEnvelope:
    task_hash: str
    worker_id: str
    target_agent: str
    capability: str
    requires_write: bool
    is_heavy: bool
    verification_required: bool
    safety_decision: str
    payload: dict[str, Any]
    correlation_id: str = ""
    task_id: str = ""
    mission_id: str = ""
    requested_model: Optional[str] = None
    native_attempt: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": "1.0", "type": "TASK", **self.__dict__}


LocalConsumer = Callable[[dict[str, Any]], dict[str, Any]]


class LocalWorkerAdapterBoundary:
    """Durable envelope -> consumer -> bound ACK + RESULT contract."""
    SUPPORTED_AGENTS = frozenset({"CLI1", "CODEX", "GEMINI"})

    def __init__(self, workspace_dir: Path, consumers: Optional[dict[str, LocalConsumer]] = None):
        self.workspace_dir = Path(workspace_dir)
        self.events_dir = self.workspace_dir / "events" / "task-envelopes"
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.consumers = dict(consumers or {})

    def register_consumer(self, agent: str, consumer: LocalConsumer) -> None:
        if agent not in self.SUPPORTED_AGENTS or not callable(consumer):
            raise ValueError("Unsupported local consumer")
        self.consumers[agent] = consumer

    def attach_real_worker_adapters(self, repo_root: Optional[Path] = None) -> None:
        """Attaches real CLI1, CODEX, and GEMINI worker adapters."""
        try:
            from scripts.courier_real_worker_adapters import get_real_worker_adapters
        except ImportError:
            from courier_real_worker_adapters import get_real_worker_adapters
        adapters = get_real_worker_adapters(repo_root)
        for agent, consumer in adapters.items():
            self.register_consumer(agent, consumer)

    def dispatch(self, agent: str, envelope: TaskEnvelope, adapters: dict[str, str]) -> dict[str, Any]:
        del adapters  # metadata is never treated as execution evidence
        consumer = self.consumers.get(agent)
        if agent not in self.SUPPORTED_AGENTS or consumer is None:
            raise RuntimeError("LOCAL_CONSUMER_NOT_REGISTERED")
        stem = f"{agent.lower()}_{envelope.task_hash}"
        task_path = self.events_dir / f"task_{stem}.json"
        ack_path = self.events_dir / f"ack_{stem}.json"
        result_path = self.events_dir / f"result_{stem}.json"
        task = envelope.to_dict()
        write_json_atomic(task_path, task)
        response = consumer(json.loads(json.dumps(task)))
        if not isinstance(response, dict):
            raise RuntimeError("MISSING_OR_INVALID_WORKER_RESPONSE")
        print("DEBUG CONSUMER IS:", type(consumer), getattr(consumer, "__name__", "unknown"))
        import inspect
        print("DEBUG CONSUMER FILE:", inspect.getfile(consumer))
        print("DEBUG RESPONSE:", response)
        ack, result = response.get("ack"), response.get("result")
        self._validate_ack(ack, envelope)
        self._validate_result(result, envelope)
        write_json_atomic(ack_path, ack); write_json_atomic(result_path, result)
        return {"dispatched_to": agent, "envelope_path": str(task_path),
                "ack_path": str(ack_path), "result_path": str(result_path),
                "worker_accepted": True, "ack_valid": True, "result_valid": True,
                "result": result}

    @staticmethod
    def _identity(kind: str, status: str, envelope: TaskEnvelope) -> dict[str, str]:
        ident = {
            "schema_version": "1.0",
            "type": kind,
            "status": status,
            "task_hash": envelope.task_hash,
            "worker_id": envelope.worker_id,
            "target_agent": envelope.target_agent,
        }
        if envelope.correlation_id:
            ident["correlation_id"] = envelope.correlation_id
        if envelope.task_id:
            ident["task_id"] = envelope.task_id
        return ident

    @classmethod
    def _validate_ack(cls, ack: Any, envelope: TaskEnvelope) -> None:
        expected = cls._identity("ACK", "ACCEPTED", envelope)
        if not isinstance(ack, dict):
            print("DEBUG: ACK NOT DICT")
            raise RuntimeError("MISSING_OR_INVALID_ACK")
        for k, v in expected.items():
            if ack.get(k) != v:
                print(f"DEBUG: ACK MISMATCH {k} expected={v} got={ack.get(k)}")
                raise RuntimeError("MISSING_OR_INVALID_ACK")

    @classmethod
    def _validate_result(cls, result: Any, envelope: TaskEnvelope) -> None:
        if not isinstance(result, dict):
            raise RuntimeError("MISSING_OR_INVALID_RESULT")
        res_status = result.get("status")
        if res_status not in {"COMPLETED", "HUMAN_GATE"}:
            raise RuntimeError(f"INVALID_RESULT_STATUS: {res_status}")
        expected = cls._identity("RESULT", res_status, envelope)
        if any(result.get(k) != v for k, v in expected.items()):
            raise RuntimeError("MISSING_OR_INVALID_RESULT_IDENTITY")
        payload = result.get("payload")
        if not isinstance(payload, dict) or result.get("result_fingerprint") != canonical_hash(payload):
            raise RuntimeError("RESULT_FINGERPRINT_MISMATCH")
        if envelope.requested_model:
            req_model = payload.get("requested_model")
            if req_model and req_model != envelope.requested_model:
                raise RuntimeError("REQUESTED_MODEL_MISMATCH")


class CourierSafetyDispatcher:
    """Single-writer/single-heavy-job dispatcher with verify-before-next."""
    FORBIDDEN_ACTIONS = {"WITHDRAW", "TRANSFER", "SEND", "PUBLISH", "PUBLICATION",
        "UPLOAD", "PAY", "PAYMENT", "PURCHASE", "BUY", "SELL", "TRADE", "SIGN",
        "WALLET_SIGN", "CONTACT_CUSTOMER", "ROTATE_ACCOUNT", "ACCOUNT_ROTATION"}
    ACTION_KEYS = {"action", "requested_action", "operation", "command"}
    ZERO_SPEND_KEYS = {"real_spend_eur", "spend_eur", "cost_eur", "amount_eur"}
    GATED_KEYS = {"external_action", "external_send", "publish", "publication", "upload",
        "customer_contact", "customer_message", "wallet_sign", "wallet_signing",
        "account_rotation", "real_trade", "live_trade", "payment", "purchase"}

    def __init__(self, workspace_dir: str | Path, adapter_boundary: Optional[Any] = None):
        self.workspace_dir = Path(workspace_dir)
        self.lease_manager = TaskLeaseManager(self.workspace_dir)
        self.ledger = ReviewLedger(self.workspace_dir)
        self.adapter_boundary = adapter_boundary or LocalWorkerAdapterBoundary(self.workspace_dir)
        self.last_task_hash = None; self.last_result_status = None
        self._inflight: dict[str, dict[str, Any]] = {}
        self.adapters = {a: "LOCAL_ADAPTER_BOUNDARY" for a in ("CLI1", "CODEX", "GEMINI")}
        self.router = DynamicAgentRouter()
        self.mission_queue = MissionQueue(self.workspace_dir)

    def attach_real_worker_adapters(self, repo_root: Optional[Path] = None) -> None:
        """Attaches real CLI1, CODEX, and GEMINI worker adapters to boundary."""
        self.adapter_boundary.attach_real_worker_adapters(repo_root)

    def evaluate_routing(self, request: str, preferred_agent: str = None) -> str:
        return self.router.select_agent(request or "analysis", preferred_agent) or ""

    def _scan_unsafe(self, data: Any, path: str = "$") -> tuple[bool, str]:
        if isinstance(data, dict):
            for raw_key, value in data.items():
                key, location = str(raw_key).strip().lower(), f"{path}.{raw_key}"
                if key in self.ZERO_SPEND_KEYS:
                    if (isinstance(value, bool) or not isinstance(value, (int, float)) or
                            not math.isfinite(float(value)) or float(value) != 0):
                        return False, f"FAIL_CLOSED: invalid/non-zero spend at {location}"
                if key in self.ACTION_KEYS:
                    if not isinstance(value, str) or value.strip().upper() in self.FORBIDDEN_ACTIONS:
                        return False, f"FAIL_CLOSED: prohibited/invalid action at {location}"
                if key in self.GATED_KEYS:
                    if isinstance(value, dict):
                        activated = any(bool(value.get(k)) for k in ("activate", "send", "contact", "execute", "enabled"))
                        activated |= str(value.get("mode", "")).upper() in {"LIVE", "REAL", "PRODUCTION"}
                        if activated: return False, f"FAIL_CLOSED: gated action at {location}"
                    elif value not in (False, None, 0, "", "false", "False"):
                        return False, f"FAIL_CLOSED: gated action at {location}"
                if key in {"trade_mode", "payment_mode", "execution_mode", "mode"} and str(value).upper() in {"LIVE", "REAL", "PRODUCTION"}:
                    return False, f"FAIL_CLOSED: live mode at {location}"
                if key in {"real_trades", "trade_count"} and (isinstance(value, bool) or not isinstance(value, int) or value != 0):
                    return False, f"FAIL_CLOSED: real trade count at {location}"
                safe, reason = self._scan_unsafe(value, location)
                if not safe: return safe, reason
        elif isinstance(data, list):
            for index, value in enumerate(data):
                safe, reason = self._scan_unsafe(value, f"{path}[{index}]")
                if not safe: return safe, reason
        return True, "SAFE"

    def is_safe_action(self, task_spec: dict[str, Any]) -> tuple[bool, str]:
        return self._scan_unsafe(task_spec) if isinstance(task_spec, dict) else (False, "FAIL_CLOSED: task_spec must be a dictionary")

    def _release(self, task_hash: str, worker_id: str) -> None:
        state = self._inflight.get(task_hash)
        if not state or state["worker_id"] != worker_id: return
        if state["requires_write"]: self.lease_manager.release_lease("global_writer_lease", worker_id)
        if state["is_heavy"]: self.lease_manager.release_lease("global_heavy_job_lease", worker_id)
        self._inflight.pop(task_hash, None)


    def retry_worker_unavailable(self, worker_id: str, mission_id: str) -> dict[str, Any]:
        mission = self.mission_queue.get(mission_id)
        if mission["status"] != "BLOCKED" or mission.get("result_reference") != "WORKER_UNAVAILABLE":
            return {"status": "FAIL", "reason": "NOT_WORKER_UNAVAILABLE"}
        old_evidence = mission.get("blocker_evidence")
        if not old_evidence:
            return {"status": "FAIL", "reason": "MISSING_OLD_EVIDENCE"}

        # Check writer conflic
        if mission.get("requires_write"):
            # A bit hacky: we can't easily check without acquiring, so we acquire and release
            got_write, _, _ = self.lease_manager.acquire_lease("global_writer_lease", "retry_check", worker_id, 1)
            if not got_write:
                return {"status": "FAIL", "reason": "WRITER_CONFLICT"}
            self.lease_manager.release_lease("global_writer_lease", worker_id)

        from scripts.worker_availability import WorkerAvailabilityResolver
        resolver = WorkerAvailabilityResolver()
        ev = resolver.resolve_gemini() if mission.get("preferred_agent") == "GEMINI" else resolver.resolve_codex()
        new_evidence = canonical_hash({"state": ev.state, "executable": ev.executable, "detail": ev.detail})

        if old_evidence == new_evidence:
            return {"status": "FAIL", "reason": "UNCHANGED_EVIDENCE"}

        try:
            self.mission_queue.retry_worker_unavailable(mission_id, old_evidence, new_evidence)
            return {"status": "PENDING", "mission_id": mission_id}
        except Exception as e:
            return {"status": "FAIL", "reason": str(e)}

    def submit_task(self, worker_id: str, task_spec: dict[str, Any], mission_id: str = "") -> dict[str, Any]:
        if self.last_result_status in {"PENDING_VERIFY", "UNKNOWN", "FAIL", "MISSING", "DISPATCH_EXCEPTION", "VERIFY_EXCEPTION"}:
            return {"status": "BLOCKED", "reason": "PREVIOUS_TASK_UNVERIFIED"}
        safe, reason = self.is_safe_action(task_spec)
        if not safe: return {"status": "FAIL_CLOSED", "reason": reason}
        task_hash = canonical_task_hash(task_spec)
        prior = self.ledger.get_reviewed_entry(task_hash)
        if prior and (not mission_id or prior.get("file_hashes", {}).get("mission_id") == mission_id):
            return {"status": "DEDUPED", "result": prior.get("review_result", "APPROVED"), "task_hash": task_hash}
        write, heavy = bool(task_spec.get("requires_write", False)), bool(task_spec.get("is_heavy", False))
        got_write = got_heavy = False
        try:
            if write:
                got_write, _, _ = self.lease_manager.acquire_lease("global_writer_lease", task_hash, worker_id, 3600)
                if not got_write: return {"status": "BLOCKED", "reason": "SECOND_WRITER_BLOCKED"}
            if heavy:
                got_heavy, _, _ = self.lease_manager.acquire_lease("global_heavy_job_lease", task_hash, worker_id, 3600)
                if not got_heavy:
                    if got_write: self.lease_manager.release_lease("global_writer_lease", worker_id)
                    return {"status": "QUEUED", "reason": "HEAVY_JOB_LIMIT_EXCEEDED"}
            target = self.evaluate_routing(task_spec.get("capability_request", ""), task_spec.get("preferred_agent"))
            if not target:
                return {"status": "BLOCKED", "reason": "NO_CAPABLE_AVAILABLE_WORKER"}
            task_id = str(task_spec.get("task_id") or "")
            correlation_id = str(task_spec.get("correlation_id") or "")
            if not mission_id:
                mission_id = str(task_spec.get("mission_id") or "")
            requested_model = task_spec.get("requested_model")
            # V10: Empty write criteria fail closed
            if write and not task_spec.get("acceptance_criteria"):
                raise ValueError("EMPTY_WRITE_CRITERIA_FAIL_CLOSED")

            prestate = {}
            if write:
                criteria = task_spec.get("acceptance_criteria", {})
                if "file_exists" in criteria:
                    from pathlib import Path
                    import os
                    ws_path = Path(self.workspace_dir).resolve()
                    # Do not resolve yet to prevent symlink traversal tricking the pre-check if we check later,
                    # but we can resolve it to safely check containment.
                    fpath = (Path(self.workspace_dir) / criteria["file_exists"]).resolve()
                    try:
                        fpath.relative_to(ws_path)
                    except ValueError:
                        raise ValueError("PATH_CONTAINMENT_VIOLATION")

                    prestate["exists"] = fpath.exists()
                    if fpath.exists():
                        try:
                            prestate["content"] = fpath.read_text(encoding="utf-8").strip()
                        except Exception:
                            prestate["content"] = None

            envelope = TaskEnvelope(
                task_hash=task_hash,
                worker_id=worker_id,
                target_agent=target,
                capability=task_spec.get("capability_request", "default"),
                requires_write=write,
                is_heavy=heavy,
                verification_required=True,
                safety_decision="APPROVED_SAFE",
                payload=task_spec,
                correlation_id=correlation_id,
                task_id=task_id,
                mission_id=mission_id,
                requested_model=requested_model,
            )
            dispatch = self.adapter_boundary.dispatch(target, envelope, self.adapters)
            self._inflight[task_hash] = {"worker_id": worker_id, "requires_write": write, "is_heavy": heavy, "result": dispatch["result"], "route": target, "task": task_spec, "mission_id": mission_id, "prestate": prestate}
            self.last_task_hash, self.last_result_status = task_hash, "PENDING_VERIFY"
            return {"status": "EXECUTED", "route": target, "dispatch_info": dispatch, "task_hash": task_hash, "requires_verify": True}
        except Exception as error:
            if got_write: self.lease_manager.release_lease("global_writer_lease", worker_id)
            if got_heavy: self.lease_manager.release_lease("global_heavy_job_lease", worker_id)
            self.last_result_status = "DISPATCH_EXCEPTION"
            return {"status": "FAIL_CLOSED", "reason": f"MISSING_ACK_OR_DISPATCH_FAIL: DISPATCH_FAILED: {error}"}


    def canonical_validate_result(self, mission_id: str, task: dict, res_data: dict, dispatched_route: str = None) -> bool:
        if not isinstance(res_data, dict): return False
        task_hash = canonical_task_hash(task)
        if res_data.get("task_hash") != task_hash: return False
        if res_data.get("mission_id") != mission_id: return False
        if res_data.get("is_stale") or res_data.get("status") in ("STALE", "SUPERSEDED", "INVALID"): return False
        if res_data.get("status") not in ("COMPLETED", "PASS", "SUCCESS"): return False
        if not res_data.get("result_fingerprint"): return False
        expected_agent = dispatched_route or task.get("preferred_agent")
        if expected_agent and res_data.get("target_agent") != expected_agent: return False
        return True
    def verify_result(self, worker_id: str, task_hash: str, verification_status: str, result_data: Any = None) -> str:
        state = self._inflight.get(task_hash)
        try:
            if not state or state["worker_id"] != worker_id or verification_status != "PASS" or result_data != state["result"]:
                self.last_result_status = "UNKNOWN" if verification_status == "UNKNOWN" else "FAIL"
                return "FAIL_CLOSED"

            attempts = 1
            max_attempts = 2

            while attempts <= max_attempts:
                if isinstance(result_data, dict):
                    if result_data.get("status") == "HUMAN_GATE" or result_data.get("payload", {}).get("verdict") in {"HUMAN_APPROVAL_REQUIRED", "HUMAN_GATE"}:
                        self.last_result_status = "HUMAN_GATE"
                        return "FAIL_CLOSED"
                    task = state.get("task", {})
                    mission_id = state.get("mission_id", "unknown")

                    if not self.canonical_validate_result(mission_id, task, result_data, state.get("route")):
                        self.last_result_status = "FAIL"
                        return "FAIL_CLOSED"

                    criteria = task.get("acceptance_criteria")
                    if state.get("requires_write") and not criteria:
                        self.last_result_status = "FAIL"
                        return "FAIL_CLOSED"

                    effect_missing = False

                    if criteria:
                        if "file_exists" in criteria:
                            from pathlib import Path
                            import os
                            ws_path = Path(self.workspace_dir).resolve()
                            fpath = (Path(self.workspace_dir) / criteria["file_exists"]).resolve()

                            # V1-V4: Path containment
                            try:
                                fpath.relative_to(ws_path)
                            except ValueError:
                                self.last_result_status = "FAIL"
                                return "FAIL_CLOSED"

                            # V9: Missing effect rejection
                            if not fpath.exists():
                                effect_missing = True

                            post_content = ""
                            if not effect_missing and "content_matches" in criteria:
                                try:
                                    post_content = fpath.read_text(encoding="utf-8").strip()
                                    if post_content != criteria["content_matches"].strip():
                                        effect_missing = True
                                except Exception:
                                    effect_missing = True

                            # V5-V8: Freshness checks
                            prestate = state.get("prestate")
                            if state.get("requires_write"):
                                if prestate is None or type(prestate) is not dict or "exists" not in prestate:
                                    self.last_result_status = "FAIL"
                                    return "FAIL_CLOSED"
                                
                            if prestate is not None:
                                was_present = prestate.get("exists", False)
                                pre_content = prestate.get("content")

                                req_content = criteria.get("content_matches", "").strip()
                                if was_present:
                                    if "content_matches" in criteria:
                                        if pre_content == req_content:
                                            # V6: Stale artifact rejection
                                            self.last_result_status = "FAIL"
                                            return "FAIL_CLOSED"
                                    else:
                                        self.last_result_status = "FAIL"
                                        return "FAIL_CLOSED"
                                        
                        if effect_missing:
                            if state.get("requires_write") and state.get("route") == "GEMINI" and attempts < max_attempts:
                                attempts += 1
                                envelope = TaskEnvelope(
                                    task_hash=task_hash,
                                    worker_id=worker_id,
                                    target_agent=state.get("route"),
                                    capability=task.get("capability_request", "default"),
                                    requires_write=True,
                                    is_heavy=state.get("is_heavy", False),
                                    verification_required=True,
                                    safety_decision="APPROVED_SAFE",
                                    payload=task,
                                    correlation_id=task.get("correlation_id", ""),
                                    native_attempt=attempts,
                                    task_id=task.get("task_id", ""),
                                    mission_id=state.get("mission_id", ""),
                                    requested_model=task.get("requested_model")
                                )
                                try:
                                    new_dispatch = self.adapter_boundary.dispatch(state.get("route"), envelope, self.adapters)
                                    result_data = new_dispatch.get("result")
                                    state["result"] = result_data
                                    continue
                                except Exception:
                                    self.last_result_status = "FAIL"
                                    return "FAIL_CLOSED"
                            else:
                                self.last_result_status = "FAIL"
                                return "FAIL_CLOSED"
                                
                    break

            executing_agent = state.get("route")
            # The dispatcher owns the supported-agent contract.  Test and production
            # boundaries need not expose an implementation-specific class attribute.
            if executing_agent not in self.adapters:
                self.last_result_status = "FAIL"
                return "FAIL_CLOSED"

            self.ledger.record_review(review_id=f"rev-{task_hash[:12]}", checkpoint_commit="CANONICAL", diff_hash=task_hash,
                file_hashes={
                    "task_hash": task_hash,
                    "mission_id": mission_id,
                    # ``worker_id`` is the agent that produced the accepted result;
                    # the coordinator is retained separately for lease provenance.
                    "worker_id": executing_agent,
                    "coordinator_worker_id": worker_id,
                    "dispatched_route": executing_agent,
                    "effect_verified": "True",
                    "freshness_verified": "True",
                    "result_fingerprint": canonical_hash(result_data),
                    "native_attempt": str(attempts),
                }, risk_class="SAFE", review_type="TASK_VERIFICATION", review_result="APPROVED",
                reviewer=executing_agent, reason="Verified identity-bound local task result")
            
            self.last_result_status = "PASS"
            return "VERIFIED_AND_CACHED"
        except Exception:
            self.last_result_status = "VERIFY_EXCEPTION"; raise
        finally:
            self._release(task_hash, worker_id)

    def process_next_mission(
        self,
        worker_id: str,
        successor_deriver: Optional[Callable[[dict[str, Any]], Optional[dict[str, Any]]]] = None,
        verification_status: str = "PASS",
        goal: Optional[str] = None,
    ) -> dict[str, Any]:
        """Run one claimed mission through the only supported local lifecycle.

        The local boundary is deliberately synchronous and deterministic: its consumer
        returns an ACK and result, then this method persists verification before it can
        derive a successor.  A missing/invalid response is a blocked mission, never a
        successful cache entry.
        """
        mission = self.mission_queue.claim_next(worker_id, goal=goal)
        if mission is None:
            return {"status": "NO_PENDING_MISSION"}
        self.last_result_status = None
        mission_id = mission["mission_id"]
        task = dict(mission.get("task", {}))
        safe, reason = self.is_safe_action(task)
        if not safe:
            self.mission_queue.transition(mission_id, "BLOCKED", claimed_by=worker_id, result_reference=reason)
            return {"status": "BLOCKED", "mission_id": mission_id, "reason": reason}
        if self._requires_human_gate(mission, task):
            import uuid, datetime
            gate_id = "GATE-" + str(uuid.uuid4())
            gate_request = {
                "gate_id": gate_id,
                "goal_id": mission.get("goal"),
                "task_id": task.get("task_id"),
                "attempt_id": mission_id,
                "gate_reason": "HUMAN_GATE_REQUIRED_BY_POLICY",
                "requested_action": task.get("action"),
                "requested_scope": task.get("goal_context"),
                "created_at": datetime.datetime.utcnow().isoformat(),
                "resolution_status": "PENDING"
            }
            self.mission_queue.transition(mission_id, "HUMAN_GATE", claimed_by=worker_id,
                                          result_reference="HUMAN_ACTION_REQUIRED", human_gate_id=gate_id,
                                          human_gate_request=gate_request)
            return {"status": "HUMAN_GATE", "mission_id": mission_id, "gate_id": gate_id}
        selected = self.router.select_agent(mission["capability_required"], mission.get("preferred_agent"))
        if selected is None:
            from scripts.worker_availability import WorkerAvailabilityResolver
            resolver = WorkerAvailabilityResolver()
            ev = resolver.resolve_gemini() if mission.get("preferred_agent") == "GEMINI" else resolver.resolve_codex()
            from scripts.courier_safety_dispatcher import canonical_hash
            ev_fingerprint = canonical_hash({"state": ev.state, "executable": ev.executable, "detail": ev.detail})
            self.mission_queue.transition(mission_id, "BLOCKED", claimed_by=worker_id,
                                          result_reference="WORKER_UNAVAILABLE", blocker_evidence=ev_fingerprint)
            return {"status": "BLOCKED", "mission_id": mission_id, "reason": "WORKER_UNAVAILABLE"}
        task["capability_request"] = mission["capability_required"]
        # The explicit selected worker is checked again by the router; no arbitrary fallback.
        original_router = self.router
        self.router = DynamicAgentRouter({selected: "AVAILABLE"})
        try:
            dispatch = self.submit_task(worker_id, task, mission_id=mission_id)
        finally:
            self.router = original_router
        if dispatch.get("status") == "DEDUPED":
            task_hash = dispatch["task_hash"]
            import glob
            import json
            from pathlib import Path
            matches = glob.glob(str(self.adapter_boundary.events_dir / f"result_*_{task_hash}.json"))
            valid_match = None
            for match in matches:
                try:
                    with open(match, "r") as f:
                        res_data = json.load(f)

                    if not isinstance(res_data, dict): continue

                    if not self.canonical_validate_result(mission_id, task, res_data, dispatch.get("route")):
                        continue

                    valid_match = match
                    break
                except Exception:
                    continue

            if valid_match:
                self.mission_queue.transition(mission_id, "RUNNING")
                self.mission_queue.transition(mission_id, "PENDING_VERIFY")
                self.mission_queue.transition(mission_id, "VERIFIED", claimed_by=worker_id, result_reference=valid_match)
                successor = self.mission_queue.derive_successor(mission_id, successor_deriver)
                return {"status": "VERIFIED", "mission_id": mission_id, "successor_mission_id": successor.get("mission_id") if successor else None, "agent_dispatched": dispatch.get("route")}
            else:
                dispatch["reason"] = "DEDUPED_BUT_RESULT_FILE_MISSING_OR_INVALID"
                dispatch["status"] = "BLOCKED"

        if dispatch.get("status") not in ("EXECUTED", "DEDUPED"):
            reason = dispatch.get("reason", "")
            if "GEMINI_NATIVE_AGY_FAILED" in reason and ("ERROR" in reason or "Model did not return schema-valid JSON payload" in reason) and task.get("action") == "discover_improvement_opportunities" and not task.get("requires_write"):
                self.last_result_status = None
                task["preferred_agent"] = "CLI1"
                task["capability_request"] = "local repo analysis"
                original_router_fallback = self.router
                self.router = DynamicAgentRouter({"CLI1": "AVAILABLE"})
                try:
                    dispatch = self.submit_task(worker_id, task, mission_id=mission_id)
                finally:
                    self.router = original_router_fallback

        if dispatch.get("status") not in ("EXECUTED", "DEDUPED"):
            self.mission_queue.transition(mission_id, "BLOCKED", claimed_by=worker_id,
                                          result_reference=dispatch.get("reason", "DISPATCH_FAILED"))
            return {"status": "BLOCKED", "mission_id": mission_id, "reason": dispatch.get("reason")}

        result_obj = dispatch.get("dispatch_info", {}).get("result", {})
        res_payload = result_obj.get("payload", {})
        res_verdict = res_payload.get("verdict")
        res_status = result_obj.get("status")

        # Human gate triggered by worker execution
        if res_status == "HUMAN_GATE" or res_verdict in {"HUMAN_APPROVAL_REQUIRED", "HUMAN_GATE"}:
            self.mission_queue.transition(
                mission_id,
                "HUMAN_GATE",
                claimed_by=worker_id,
                result_reference=f"HUMAN_APPROVAL_REQUIRED: {res_payload.get('summary', 'Human approval required')}",
            )
            self._release(dispatch["task_hash"], worker_id)
            return {"status": "HUMAN_GATE", "mission_id": mission_id, "successor_mission_id": None}

        self.mission_queue.transition(mission_id, "RUNNING", claimed_by=worker_id,
                                      result_reference=dispatch["dispatch_info"]["result_path"])
        self.mission_queue.transition(mission_id, "PENDING_VERIFY", claimed_by=worker_id)
        try:
            verified = self.verify_result(worker_id, dispatch["task_hash"], verification_status, dispatch["dispatch_info"]["result"])
        except Exception:
            self.mission_queue.transition(mission_id, "BLOCKED", claimed_by=worker_id,
                                          result_reference="VERIFY_EXCEPTION")
            return {"status": "BLOCKED", "mission_id": mission_id, "reason": "VERIFY_EXCEPTION"}
        if verified != "VERIFIED_AND_CACHED":
            state = "BLOCKED" if verification_status == "UNKNOWN" else "FAILED"
            self.mission_queue.transition(mission_id, state, claimed_by=worker_id,
                                          result_reference=f"VERIFICATION_{verification_status}_FAIL_CLOSED")
            return {"status": state, "mission_id": mission_id}
        self.mission_queue.transition(mission_id, "VERIFIED", claimed_by=worker_id,
                                      verification_reference=dispatch["task_hash"])
        successor = self.mission_queue.derive_successor(mission_id, successor_deriver)
        return {"status": "VERIFIED", "mission_id": mission_id, "successor_mission_id": successor.get("mission_id") if successor else None, "agent_dispatched": dispatch.get("route")}

    @staticmethod
    def _requires_human_gate(mission: dict[str, Any], task: dict[str, Any]) -> bool:
        res = mission.get("human_gate_resolution")
        if res and res.get("status") == "APPROVED":
            if res.get("authorized_action") == task.get("action") and res.get("authorized_scope") == task.get("goal_context"):
                return False
        if task.get("human_gate_required") or mission.get("human_gate_required"):
            return True
        if task.get("action") == "discover_improvement_opportunities":
            return False

        import re
        task_parts = []
        for k, v in task.items():
            if k not in ("files", "target_files", "changed_files", "task_hash", "correlation_id", "mission_id", "task_id", "result", "result_data"):
                task_parts.append(str(v))

        raw_text = " ".join(str(x) for x in (mission.get("goal", ""), mission.get("normalized_task", ""), " ".join(task_parts)))
        
        # Strip all file paths / identifiers ending in extensions or containing slashes to avoid false positives
        import re
        raw_text = re.sub(r'\b[\w\.-]+/[\w\.-]+\.(?:py|json|md|txt|mjs|js|ts|sh|yaml|yml)\b', '', raw_text) # strip things like tests/test_deploy.py
        raw_text = re.sub(r'\b[\w\.-]+\.(?:py|json|md|txt|mjs|js|ts|sh|yaml|yml)\b', '', raw_text) # strip things like test_deploy.py
        text = raw_text.lower()
        
        # Action-aware gating (fails closed on contradictions)
        gated_action_patterns = [
            r'\b(?:deploy|deploying)\s+(?:production|prod|external|now|to\s+prod|to\s+production)\b',
            r'\b(?:login|log\s+in|logging\s+in)\b',
            r'\b(?:authenticate|authenticating)\s+(?:to|against|with|external)\b',
            r'\b(?:publish|publishing)\s+(?:this|externally|production|to)\b',
            r'\b(?:purchase|purchasing|buy|buying|pay|paying|upgrade)[\s/]+(?:paid|capacity|subscription|billing)\b',
            r'\b(?:enable|setup)\s+(?:billing|purchases)\b',
            r'\b(?:sign|signing)\s+(?:wallet|transaction)\b',
            r'\b(?:perform|execute|do)\s+(?:wallet|real-money|trade)\b',
            r'\breal-money\s+trade\b',
            r'\bwallet\s+signing\b',
            r'\b(?:contact|email|message)\s+(?:customers?|users?)\b',
            r'\bhuman_gate\s+required\b',
            r'\b(?:password|2fa|captcha|touch\s+id|face\s+id|sudo|admin|uac)\s+(?:required|needed|prompt)\b',
            r'\b(?:enter|use|provide|type|submit|bypass|solve|verify)\s+(?:a\s+)?(?:password|2fa|captcha|touch\s+id|face\s+id|sudo|admin|uac)\b',
            r'\b(?:keychain|credential)\s+(?:unlock|reset)\b',
            r'\bgithub\s+login\b',
            r'\b(?:kyc|legal\s+acceptance)\b',
            r'\breal\s+spend\b',
            r'\breal\s+trades?\b',
            r'\bcustomer\s+contact\b',
            r'\bexternal\s+send\b',
            r'\boauth\s+login\b',
            r'\b(?:connect|use)\s+(?:my\s+|a\s+)?real\s+wallet\b'
        ]
        
        negation_prefix = r'\b(?:no|not|do\s+not|never|without)\s+(?:a\s+|any\s+|my\s+)?$'
        
        for pat in gated_action_patterns:
            for match in re.finditer(pat, text):
                prefix = text[max(0, match.start() - 15):match.start()]
                if not re.search(negation_prefix, prefix):
                    return True
                
        return False


@dataclass(frozen=True)
class MissionRecord:
    mission_id: str
    parent_mission_id: Optional[str]
    goal: str
    normalized_task: str
    capability_required: str
    preferred_agent: str
    requires_write: bool
    is_heavy: bool
    risk_class: str
    verification_required: bool
    status: str
    task_hash: str
    created_at: floa
    claimed_by: Optional[str] = None
    result_reference: Optional[str] = None
    verification_reference: Optional[str] = None
    next_mission_reference: Optional[str] = None
    task: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


class MissionQueue:
    """A small persistent, single-writer lifecycle queue.

    Queue mutations hold an O_EXCL lock and replace the complete JSON document.  The
    lock is intentionally fail-closed: a busy or malformed queue cannot be guessed
    through as a successful claim.
    """
    STATES = frozenset({"PENDING", "CLAIMED", "RUNNING", "PENDING_VERIFY", "VERIFIED",
                        "FAILED", "BLOCKED", "HUMAN_GATE", "DEDUPED"})
    TRANSITIONS = {
        "PENDING": {"CLAIMED", "BLOCKED", "HUMAN_GATE", "DEDUPED"},
        "CLAIMED": {"RUNNING", "BLOCKED", "HUMAN_GATE", "DEDUPED"},
        "RUNNING": {"PENDING_VERIFY", "FAILED", "BLOCKED", "HUMAN_GATE"},
        "PENDING_VERIFY": {"VERIFIED", "FAILED", "BLOCKED", "HUMAN_GATE"},
        "VERIFIED": set(), "FAILED": set(), "BLOCKED": {"PENDING"}, "HUMAN_GATE": set(), "DEDUPED": set(),
    }
    REQUIRED_FIELDS = frozenset({"mission_id", "parent_mission_id", "goal", "normalized_task",
        "capability_required", "preferred_agent", "requires_write", "is_heavy", "risk_class",
        "verification_required", "status", "task_hash", "created_at", "claimed_by",
        "result_reference", "verification_reference", "next_mission_reference"})

    def __init__(self, workspace_dir: str | Path):
        self.queue_file = Path(workspace_dir) / "events" / "mission-queue" / "queue.json"
        self.lock_file = self.queue_file.with_suffix(".lock")
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.queue_file.exists():
            write_json_atomic(self.queue_file, {"schema_version": "1.0", "missions": []})

    def _lock(self) -> int:
        try:
            return os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise RuntimeError("MISSION_QUEUE_BUSY_FAIL_CLOSED") from error

    def _unlock(self, fd: int) -> None:
        try: os.close(fd)
        finally: self.lock_file.unlink(missing_ok=True)

    def _document(self) -> dict[str, Any]:
        try:
            with open(self.queue_file, encoding="utf-8") as handle: document = json.load(handle)
        except Exception as error:
            raise RuntimeError("MISSION_QUEUE_CORRUPT_FAIL_CLOSED") from error
        if isinstance(document, list):  # read only legacy shape, then migrate on first mutation
            document = {"schema_version": "1.0", "missions": document}
        if not isinstance(document, dict) or not isinstance(document.get("missions"), list):
            raise RuntimeError("MISSION_QUEUE_CORRUPT_FAIL_CLOSED")
        return document

    def _mutate(self, fn: Callable[[dict[str, Any]], Any]) -> Any:
        fd = self._lock()
        try:
            document = self._document()
            
            import copy
            before = copy.deepcopy(document)
            
            outcome = fn(document)
            
            print(f"DEBUG _mutate fn={fn.__name__} outcome={outcome}")
            print(f"DEBUG _mutate before missions: {[m.get('mission_id') for m in before.get('missions', [])]}")
            print(f"DEBUG _mutate after missions: {[m.get('mission_id') for m in document.get('missions', [])]}")
            
            write_json_atomic(self.queue_file, document)
            return outcome
        finally:
            self._unlock(fd)

    @staticmethod
    def _mission(document: dict[str, Any], mission_id: str) -> dict[str, Any]:
        for mission in document["missions"]:
            if mission.get("mission_id") == mission_id: return mission
        raise KeyError("MISSION_NOT_FOUND")

    @classmethod
    def _validate(cls, mission: dict[str, Any]) -> None:
        if not isinstance(mission, dict) or not cls.REQUIRED_FIELDS.issubset(mission):
            raise ValueError("INVALID_MISSION_RECORD")
        if mission["status"] not in cls.STATES or not isinstance(mission["task_hash"], str) or not mission["task_hash"]:
            raise ValueError("INVALID_MISSION_RECORD")

    def enqueue(self, mission_dict: dict[str, Any]) -> dict[str, Any]:
        mission = self._normalize(mission_dict)
        def add(document: dict[str, Any]) -> dict[str, Any]:
            if any(item.get("mission_id") == mission["mission_id"] for item in document["missions"]):
                raise ValueError("DUPLICATE_MISSION_ID")
            document["missions"].append(mission); return dict(mission)
        return self._mutate(add)

    def _normalize(self, mission: dict[str, Any]) -> dict[str, Any]:
        task = dict(mission.get("task") or {})
        task.setdefault("capability_request", str(mission.get("capability_required", "analysis")))
        cap = str(mission.get("capability_required", "analysis"))
        if "capability_request" not in task:
            task["capability_request"] = cap
        task["preferred_agent"] = mission.get("preferred_agent", "")
        if mission.get("requires_write"):
            task.setdefault("requires_write", True)
        if mission.get("is_heavy"):
            task.setdefault("is_heavy", True)
        goal = str(mission.get("goal", "")).strip()
        normalized = str(mission.get("normalized_task", goal)).strip()
        record = MissionRecord(
            mission_id=str(mission.get("mission_id") or uuid.uuid4()), parent_mission_id=mission.get("parent_mission_id"),
            goal=goal, normalized_task=normalized, capability_required=cap,
            preferred_agent=str(mission.get("preferred_agent", "")), requires_write=bool(mission.get("requires_write", False)),
            is_heavy=bool(mission.get("is_heavy", False)), risk_class=str(mission.get("risk_class", "SAFE")),
            verification_required=bool(mission.get("verification_required", True)), status=str(mission.get("status", "PENDING")),
            task_hash=str(mission.get("task_hash") or canonical_task_hash(task)), created_at=float(mission.get("created_at", time.time())),
            claimed_by=mission.get("claimed_by"), result_reference=mission.get("result_reference"),
            verification_reference=mission.get("verification_reference"), next_mission_reference=mission.get("next_mission_reference"), task=task,
        ).to_dict()
        self._validate(record)
        if record["status"] != "PENDING": raise ValueError("NEW_MISSION_MUST_BE_PENDING")
        return record

    def read_all(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._document()["missions"]]

    def get(self, mission_id: str) -> dict[str, Any]:
        return dict(self._mission(self._document(), mission_id))


    def retry_worker_unavailable(self, mission_id: str, old_evidence: str, new_evidence: str) -> dict[str, Any]:
        def apply(document: dict[str, Any]) -> dict[str, Any]:
            mission = self._mission(document, mission_id)
            if mission["status"] != "BLOCKED":
                raise RuntimeError("ONLY_BLOCKED_MISSIONS_CAN_RETRY")
            if mission.get("result_reference") != "WORKER_UNAVAILABLE":
                raise RuntimeError("ONLY_WORKER_UNAVAILABLE_CAN_RETRY")
            if old_evidence == new_evidence:
                raise RuntimeError("WORKER_UNAVAILABLE_RETRY_REQUIRES_CHANGED_EVIDENCE")
            consumed = mission.get("retry_consumed_for_transition", [])
            transition_key = f"{old_evidence}->{new_evidence}"
            if transition_key in consumed:
                raise RuntimeError("WORKER_UNAVAILABLE_RETRY_CONSUMED")
            consumed.append(transition_key)
            mission["retry_consumed_for_transition"] = consumed
            mission["status"] = "PENDING"
            self._validate(mission)
            return dict(mission)
        return self._mutate(apply)

    def transition(self, mission_id: str, new_state: str, **fields: Any) -> dict[str, Any]:
        if new_state not in self.STATES: raise ValueError("INVALID_MISSION_STATE")
        def apply(document: dict[str, Any]) -> dict[str, Any]:
            mission = self._mission(document, mission_id)
            if new_state not in self.TRANSITIONS.get(mission["status"], set()):
                raise RuntimeError("INVALID_MISSION_TRANSITION_FAIL_CLOSED")
            if mission["status"] == "BLOCKED" and new_state == "PENDING":
                if mission.get("result_reference") != "WORKER_UNAVAILABLE":
                    raise RuntimeError("INVALID_MISSION_TRANSITION_FAIL_CLOSED")
            mission.update(fields); mission["status"] = new_state
            self._validate(mission); return dict(mission)
        return self._mutate(apply)

    def claim_next(self, worker_id: str, goal: Optional[str] = None) -> Optional[dict[str, Any]]:
        def claim(document: dict[str, Any]) -> Optional[dict[str, Any]]:
            for mission in document["missions"]:
                if mission.get("status") == "PENDING":
                    if goal is not None and mission.get("goal") != goal:
                        continue
                    mission["status"], mission["claimed_by"] = "CLAIMED", worker_id
                    return dict(mission)
            return None
        return self._mutate(claim)

    def derive_successor(self, parent_id: str, deriver: Optional[Callable[[dict[str, Any]], Optional[dict[str, Any]]]]) -> Optional[dict[str, Any]]:
        def derive(document: dict[str, Any]) -> Optional[dict[str, Any]]:
            parent = self._mission(document, parent_id)
            if parent["status"] != "VERIFIED" or parent.get("next_mission_reference"):
                return None
            raw = deriver(dict(parent)) if deriver else None
            if raw is None: return None
            raw = dict(raw); raw["parent_mission_id"] = parent_id
            raw["status"] = "PENDING"
            successor = self._normalize(raw)
            if any(item.get("mission_id") == successor["mission_id"] for item in document["missions"]):
                raise RuntimeError("DUPLICATE_SUCCESSOR_FAIL_CLOSED")
            parent["next_mission_reference"] = successor["mission_id"]
            document["missions"].append(successor)
            return dict(successor)
        return self._mutate(derive)

    # Compatibility helper; it still uses transition validation.
    def update(self, mission_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        if "status" not in updates: raise RuntimeError("STATUS_TRANSITION_REQUIRED")
        updates = dict(updates); state = updates.pop("status")
        return self.transition(mission_id, state, **updates)



    def resolve_human_gate(self, gate_id: str, goal_id: str, task_id: str, attempt_id: str,
                           authorized_action: str, authorized_scope: str,
                           resolved_by: str, resolution_status: str, evidence: str = "") -> dict[str, Any]:
        def apply(document: dict[str, Any]) -> dict[str, Any]:
            mission = self._mission(document, attempt_id)
            if mission["status"] != "HUMAN_GATE": raise RuntimeError("GATE_NOT_PENDING")
            req = mission.get("human_gate_request", {})
            if not req: raise RuntimeError("MISSING_IMMUTABLE_GATE_REQUEST")
            if req.get("gate_id") != gate_id: raise RuntimeError("WRONG_GATE_ID")
            if req.get("goal_id") != goal_id: raise RuntimeError("WRONG_GOAL_ID")
            if req.get("task_id") != task_id: raise RuntimeError("WRONG_TASK_ID")
            if req.get("attempt_id") != attempt_id: raise RuntimeError("WRONG_ATTEMPT_ID")
            
            if authorized_action != req.get("requested_action"): raise RuntimeError("SCOPE_ESCALATION_REJECTED")
            if authorized_scope != req.get("requested_scope"): raise RuntimeError("SCOPE_ESCALATION_REJECTED")

            if mission.get("human_gate_resolution"): raise RuntimeError("APPROVAL_REPLAY_SAFE")
            
            if resolution_status == "APPROVED":
                mission["human_gate_resolution"] = {
                    "gate_id": gate_id, "status": "APPROVED",
                    "authorized_action": authorized_action, "authorized_scope": authorized_scope,
                    "resolved_by": resolved_by, "resolved_at": __import__("datetime").datetime.utcnow().isoformat(), "evidence": evidence
                }
                mission["status"] = "PENDING"
            else:
                mission["human_gate_resolution"] = {
                    "gate_id": gate_id, "status": "REJECTED",
                    "resolved_by": resolved_by, "resolved_at": __import__("datetime").datetime.utcnow().isoformat(), "evidence": evidence
                }
                mission["status"] = "BLOCKED"
                mission["result_reference"] = "HUMAN_GATE_REJECTED"
            self._validate(mission)
            return dict(mission)
        return self._mutate(apply)

class DynamicAgentRouter:
    """Explicit compatibility matrix; no arbitrary AVAILABLE-worker fallback.

    CLI1 = READ-ONLY (local repo analysis, deterministic checks, verification)
    GEMINI = PRIMARY BUILDER + SOLE WRITER (implementation, architecture, code)
    CODEX = EXPENSIVE_SPECIALIST only
    """
    CAPABILITIES = {
        "CLI1": ("local repo analysis", "deterministic checks", "repo verification"),
        # CODEX handles specialist work requiring deep structural analysis.
        # It does NOT receive ordinary implementation, analysis, or refactoring.
        # These keywords must appear explicitly in mission capability_required fields.
        "CODEX": (
            "legacy implementation",
            "specialist architecture",
            "state-machine repair",
            "provenance audit",
            "concurrency repair",
            "complex integration specialist",
            "ambiguous root cause specialist",
            "high-information-gain specialist",
        ),
        "GEMINI": ("analysis", "planning", "independent review", "acceptance review", "architecture", "implementation", "refactor", "debugging", "tests", "code", "google"),
    }
    VALID_STATES = frozenset({"AVAILABLE", "BUSY", "BLOCKED"})

    def __init__(self, worker_status: Optional[dict[str, str]] = None):
        self.worker_status = {agent: "AVAILABLE" for agent in self.CAPABILITIES}
        for agent, state in (worker_status or {}).items(): self.set_worker_state(agent, state)

    def set_worker_state(self, agent: str, state: str) -> None:
        if agent not in self.CAPABILITIES or state not in self.VALID_STATES: raise ValueError("INVALID_WORKER_STATE")
        self.worker_status[agent] = state

    def compatible_agents(self, capability: str) -> list[str]:
        text = str(capability).lower()
        return [agent for agent, capabilities in self.CAPABILITIES.items()
                if any(term in text for term in capabilities)]

    def evaluate(self, capability: str) -> Optional[str]:
        compatible = self.compatible_agents(capability)
        return compatible[0] if compatible else None

    def select_agent(self, capability: str, preferred_agent: Optional[str] = None) -> Optional[str]:
        """Return the best AVAILABLE worker for the requested capability.

        Uses the canonical WorkerAvailabilityResolver for GEMINI so tha
        executable presence is always re-checked at routing time.  Does NOT
        fall back from an unavailable GEMINI to CLI1 for implementation work —
        CLI1 is READ-ONLY and must not perform arbitrary writes.
        """
        from scripts.worker_availability import WorkerAvailabilityResolver, WorkerState

        resolver = WorkerAvailabilityResolver()

        compatible = self.compatible_agents(capability)

        # Honour preferred_agent first if it is compatible and available.
        if preferred_agent in compatible:
            if self._worker_executable_available(preferred_agent, resolver):
                if self.worker_status.get(preferred_agent) == "AVAILABLE":
                    return preferred_agent

        # Fall through remaining compatible workers in declaration order.
        for agent in compatible:
            if agent == preferred_agent:
                continue
            if self._worker_executable_available(agent, resolver):
                if self.worker_status.get(agent) == "AVAILABLE":
                    return agent

        return None

    @staticmethod
    def _worker_executable_available(agent: str, resolver) -> bool:
        """Check real executable availability for workers that need an external binary."""
        if agent == "GEMINI":
            evidence = resolver.resolve_gemini()
            return evidence.state == "AVAILABLE"
        # CLI1 is intrinsically available (local Python); CODEX availability is
        # checked only when it is a compatible candidate.
        if agent == "CODEX":
            evidence = resolver.resolve_codex()
            return evidence.state == "AVAILABLE"
        return True  # CLI1 and any intrinsic workers
