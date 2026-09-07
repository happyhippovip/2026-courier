import json
import uuid
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Any, Callable, Union

# Assume existing architecture imports
from scripts.courier_safety_dispatcher import (
    write_json_atomic, canonical_hash, CourierSafetyDispatcher, MissionQueue, DynamicAgentRouter
)

@dataclass
class GoalRecord:
    goal_id: str
    source: str
    goal: str
    priority: int
    constraints: list[str]
    created_at: float
    status: str  # PENDING, ACTIVE, SATISFIED, FAILED, BLOCKED

    def to_dict(self):
        return asdict(self)

class MultiChatGoalIntake:
    def __init__(self, workspace_dir: str):
        pass
        self.workspace_dir = Path(workspace_dir)
        self.db_file = self.workspace_dir / "events" / "founder-mode" / "goals.json"
        self.lock_file = self.workspace_dir / "events" / "founder-mode" / "goals.lock"
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_file.exists():
            write_json_atomic(self.db_file, [])

    def _lock(self) -> int:
        import os
        try:
            return os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as error:
            raise RuntimeError("GOAL_INTAKE_BUSY_FAIL_CLOSED") from error

    def _unlock(self, fd: int) -> None:
        import os
        os.close(fd)
        try:
            os.remove(self.lock_file)
        except OSError:
            pass

    def _mutate(self, fn):
        import json
        fd = self._lock()
        try:
            with open(self.db_file, "r") as f:
                data = json.load(f)
            outcome = fn(data)
            write_json_atomic(self.db_file, data)
            return outcome
        finally:
            self._unlock(fd)

    def _read_no_lock(self) -> list:
        import json
        with open(self.db_file, "r") as f:
            return json.load(f)

    def submit_goal(self, source: str, goal: str, priority: int = 1, constraints: Optional[list] = None) -> str:
        from scripts.courier_safety_dispatcher import MissionQueue
        def _add(data):
            goal_hash = canonical_hash(goal.strip().lower())
            for existing in data:
                if canonical_hash(existing["goal"].strip().lower()) == goal_hash and existing["status"] in ["PENDING", "ACTIVE", "HUMAN_GATE", "BLOCKED"]:
                    # Deduped goal. Only reset BLOCKED/WORKER_UNAVAILABLE missions — never HUMAN_GATE or FAILED.
                    q = MissionQueue(self.workspace_dir)
                    def _unblock_worker_unavailable_only(doc):
                        changed = False
                        for m in doc.get("missions", []):
                            if m.get("goal") == existing["goal"]:
                                # HUMAN_GATE and FAILED must NEVER be auto-reset by duplicate goal intake.
                                # Only BLOCKED missions specifically due to WORKER_UNAVAILABLE may be retried.
                                if m.get("status") == "BLOCKED" and m.get("result_reference") == "WORKER_UNAVAILABLE":
                                    m["status"] = "PENDING"
                                    changed = True
                        return changed
                    q._mutate(_unblock_worker_unavailable_only)

                    # Do NOT blindly reset ACTIVE goals.
                    # Let pop_next_goal or stale recovery handle trapped ACTIVE goals.
                    return existing["goal_id"]

            goal_id = str(uuid.uuid4())
            record = GoalRecord(
                goal_id=goal_id, source=source, goal=goal.strip(), priority=priority,
                constraints=constraints or [], created_at=time.time(), status="PENDING"
            )
            data.append(record.to_dict())
            data.sort(key=lambda x: x["priority"], reverse=True)
            return goal_id
        return self._mutate(_add)

    def pop_next_goal(self) -> Optional[dict]:
        def _pop(data):
            from scripts.worker_availability import WorkerAvailabilityResolver
            from scripts.courier_safety_dispatcher import MissionQueue
            
            resolver = WorkerAvailabilityResolver()
            current_gemini = resolver.resolve_gemini().to_dict()
            
            q = MissionQueue(self.workspace_dir)
            missions = q.read_all()
            
            for g in data:
                if g["status"] == "ACTIVE":
                    # Stale ACTIVE recovery
                    has_live = any(m.get("goal") == g["goal"] and m.get("status") in ("PENDING", "RUNNING", "PENDING_VERIFY") for m in missions)
                    if not has_live:
                        has_blocked = any(m.get("goal") == g["goal"] and m.get("status") == "BLOCKED" and m.get("result_reference") == "WORKER_UNAVAILABLE" for m in missions)
                        if has_blocked:
                            g["status"] = "BLOCKED"
                        else:
                            # Stale ACTIVE with no live or blocked missions means the orchestrator crashed.
                            # Reset to PENDING so it can be picked up again.
                            g["status"] = "PENDING"

            # Then, check if any BLOCKED goals are now unblocked due to changed evidence
            for g in data:
                if g["status"] == "BLOCKED" and "blocker_evidence" in g:
                    ev = g["blocker_evidence"]
                    if "worker_evidence" in ev:
                        if current_gemini != ev["worker_evidence"]:
                            # Evidence changed! We can retry.
                            g["status"] = "ACTIVE"
                            g["blocker_evidence"]["worker_evidence"] = current_gemini
                            
                            def _unblock_mission(doc):
                                changed = False
                                for m in doc.get("missions", []):
                                    if m.get("goal") == g["goal"] and m.get("status") == "BLOCKED" and m.get("result_reference") == "WORKER_UNAVAILABLE":
                                        m["status"] = "PENDING"
                                        changed = True
                                return changed
                            q._mutate(_unblock_mission)
                            
                            return g
            
            # Then check for PENDING
            for g in data:
                if g["status"] == "PENDING":
                    g["status"] = "ACTIVE"
                    return g
            return None
        return self._mutate(_pop)

    def reopen_invalidated_blocker(self, goal_id: str, invalidation_evidence: dict = None) -> bool:
        if not invalidation_evidence:
            return False
        reason = invalidation_evidence.get("reason")
        provenance = invalidation_evidence.get("provenance")
        defect_repaired = invalidation_evidence.get("defect_repaired")
        if not reason or not provenance or not defect_repaired:
            return False
            
        def _reopen(data):
            for r in data:
                if r["goal_id"] == goal_id and r["status"] in ("BLOCKED", "FAILED", "HUMAN_GATE"):
                    # Check if the blocker was a genuine human gate that cannot be reopened
                    blocker_ev = r.get("blocker_evidence", {})
                    # If it was a genuine external gate, it cannot be reopened
                    gate_type = str(blocker_ev.get("gate_type", "")).upper()
                    if gate_type in ("OAUTH", "LOGIN", "PAYMENT", "DEPLOYMENT", "PUBLICATION", "REAL_TRADE", "WALLET_SIGNING", "KYC"):
                        return False
                        
                    r["status"] = "PENDING"
                    r["invalidation_evidence"] = invalidation_evidence
                    return True
            return False
        return self._mutate(_reopen)

    def set_status(self, goal_id: str, status: str, blocker_evidence: dict = None):
        def _update(data):
            for g in data:
                if g["goal_id"] == goal_id:
                    g["status"] = status
                    if blocker_evidence:
                        g["blocker_evidence"] = blocker_evidence
                    return True
            raise KeyError(f"Goal {goal_id} not found")
        self._mutate(_update)

    def mark_satisfied(self, goal_id: str):
        def _mark(data):
            for g in data:
                if g["goal_id"] == goal_id:
                    g["status"] = "SATISFIED"
                    return True
            raise KeyError(f"Goal {goal_id} not found")
        self._mutate(_mark)

@dataclass
class LessonRecord:
    lesson_id: str
    goal: str
    task: str
    result: str
    error: str
    root_cause: str
    lesson: str
    reusable_pattern: str
    fingerprint: str
    created_at: float

    def to_dict(self):
        return asdict(self)

class ExperienceMemory:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir)
        self.db_file = self.workspace_dir / "events" / "experience-memory" / "memory.json"
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_file.exists():
            write_json_atomic(self.db_file, [])

    def record_lesson(self, goal: str, task: str, result: str, error: str, root_cause: str, lesson: str, reusable_pattern: str) -> str:
        data = self._read()
        fingerprint = canonical_hash({"t": task, "l": lesson, "p": reusable_pattern})
        
        for ex in data:
            if ex["fingerprint"] == fingerprint:
                return ex["lesson_id"]

        lesson_id = str(uuid.uuid4())
        record = LessonRecord(
            lesson_id=lesson_id, goal=goal, task=task, result=result, error=error,
            root_cause=root_cause, lesson=lesson, reusable_pattern=reusable_pattern,
            fingerprint=fingerprint, created_at=time.time()
        )
        data.append(record.to_dict())
        self._write(data)
        return lesson_id

    def _read(self) -> list[dict]:
        with open(self.db_file, "r") as f:
            return json.load(f)

    def _write(self, data: list[dict]):
        write_json_atomic(self.db_file, data)

    def search_lessons(self, query: str) -> list[dict]:
        data = self._read()
        query = query.lower()
        return [l for l in data if query in l["goal"].lower() or query in l["task"].lower() or query in l["lesson"].lower()]



class FounderModePlanner:
    def is_strictly_satisfied(self, goal_record: dict, last_mission: dict, last_result: dict) -> bool:
        """
        Strict evidence-based satisfaction path.
        Fails closed if any condition is ambiguous.
        """
        print(f"DEBUG strictly check: result_hash={last_result.get('task_hash')} mission_hash={last_mission.get('task_hash')} type={last_result.get('task_type')} finding_id={last_result.get('finding', {}).get('finding_id')}")
        if not isinstance(last_result, dict):
            return False
            
        if last_result.get("task_type") != "DISCOVERY":
            return False
            
        payload = last_result.get("payload", {})
        finding = last_result.get("finding", {})
        
        # - evidence belongs to the CURRENT goal_id
        # - no cross-goal bleed is possible
        if last_mission.get("goal") != goal_record.get("goal"):
            return False
            
        # - evidence belongs to the CURRENT fingerprint/workspace state
        # - evidence is fresh for the current run
        # - no historical PASS from another goal/fingerprint is reused
        # Ensure task_hash strictly matches between mission and result payload
        if last_result.get("task_hash") != last_mission.get("task_hash"):
            return False
            
        # - no unresolved blocker exists
        # - no HUMAN_GATE / external-action / safety gate is present
        verdict = payload.get("verdict", "")
        if verdict in ("BLOCKED", "HUMAN_GATE", "FAIL", "ERROR"):
            return False
        if payload.get("error_type"):
            return False
            
        # - all current acceptance criteria are explicitly satisfied
        # - no implementation step is required
        finding_id = finding.get("finding_id", "UNKNOWN").upper()
        desc = finding.get("description", "").lower()
        
        is_satisfied = False
        if finding_id in ("NONE", "SATISFIED", "NO_MORE_WORK", "NO_COHERENT_GAP"):
            is_satisfied = True
            
        if not is_satisfied:
            return False
            
        return True

    def evaluate_success(self, goal_record: dict, last_result: dict, completed_missions: list = None) -> bool:
        if not completed_missions: return False
        last_mission = completed_missions[-1]
        res = self._load_result(last_mission)
        return self.is_strictly_satisfied(goal_record, last_mission, res)

    def __init__(self, workspace_dir):
        self.workspace_dir = workspace_dir
        
    def _load_result(self, mission: dict) -> dict:
        """Load and semantically classify the result stored for a mission.

        Classification is based on the ``action`` / ``stage`` fields in the
        payload, NOT on the identity of the worker that produced the result.
        This makes the classifier robust to worker routing changes.
        """
        import json
        from pathlib import Path
        ref = mission.get("result_reference")
        res = mission.get("result_data", {})
        if ref and isinstance(ref, str):
            print(f"DEBUG _load_result: ref={ref} exists={Path(ref).exists()} absolute={Path(ref).absolute()}")
        if ref and isinstance(ref, str) and Path(ref).exists():
            try:
                with open(ref, "r") as f:
                    data = json.load(f)
                payload = data.get("result", {}).get("payload", data.get("payload", {}))

                action = payload.get("action", "")
                stage = payload.get("stage", "")

                # DISCOVERY — any worker that reported a discovery action
                if action == "discover_improvement_opportunities" or "DISCOVERY" in stage.upper():
                    finding_id = payload.get("weakness_id", payload.get("finding_id", "UNKNOWN"))
                    desc = payload.get("description", "").lower()
                    if finding_id == "GENERAL_IMPROVEMENT" or finding_id == "UNKNOWN":
                        if "no coherent gap" in desc or "already satisfied" in desc or "fully operational" in desc or "no regressions or capability duplications" in desc:
                            finding_id = "NO_COHERENT_GAP"

                    res = {
                        "task_type": "DISCOVERY",
                        "task_hash": data.get("result", {}).get("task_hash", data.get("task_hash", "")), "payload": payload, "verdict": payload.get("verdict", data.get("verdict", "PASS")),
                        "goal_satisfied": payload.get("goal_satisfied", False),
                        "finding": {
                            "finding_id": finding_id,
                            "description": payload.get("description", ""),
                            "evidence": str(payload.get("evidence", "")),
                            "affected_files": payload.get("suggested_files", payload.get("affected_files", [])),
                            "recommended_action": payload.get("recommended_action", "Fix weakness"),
                            "verification_strategy": payload.get("verification_strategy", ""),
                            "confidence": payload.get("confidence", 1.0)
                        }
                    }
                    print("DEBUG _load_result returning DISCOVERY:", res)

                # VERIFICATION — explicit verification action or stage
                elif action == "verify_improvement_tests" or "VERIFICATION" in stage.upper() or "ACCEPTANCE_AUDIT" in stage.upper():
                    res = {
                        "task_type": "VERIFICATION",
                        "acceptance_evidence": {"goal_satisfied": payload.get("goal_satisfied") is True, "tests_passed": payload.get("test_returncode") == 0 or payload.get("verdict") == "PASS"}
                    }

                # IMPLEMENTATION — explicit implementation action/stage with changed files
                elif (
                    action in ("implementation", "implement")
                    or "IMPLEMENTATION" in stage.upper()
                    or payload.get("changed_files")
                ):
                    changed = payload.get("changed_files") or ["auto_detected_changes"]
                    res = {
                        "task_type": "IMPLEMENTATION",
                        "changed_files": changed if isinstance(changed, list) else [changed],
                    }

            except Exception:
                pass
        return res

    def _extract_acceptance_criteria(self, goal_text: str) -> dict:
        import re
        match = re.search(r"file named (\S+) containing exactly:\s*(.*)", goal_text, re.IGNORECASE)
        if match:
            return {"file_exists": match.group(1), "content_matches": match.group(2)}
        return {}

    def discover_and_plan(self, goal_record: dict, completed_missions: list = None) -> list:
        goal_text = goal_record["goal"]
        completed = completed_missions or []

        if not completed:
            return [{
                "goal": goal_text,
                "normalized_task": "Analyze repo state to identify improvements.",
                "capability_required": "local repo analysis",
                "preferred_agent": "GEMINI",
                "is_heavy": False,
                "requires_write": False,
                "is_heavy": True,
                "task": {
                    "action": "discover_improvement_opportunities",
                    "goal_context": goal_text,
                    "capability_request": "local repo analysis"
                }
            }]

        last_mission = completed[-1]
        last_result = self._load_result(last_mission)
        print(f"DEBUG strictly check: result_hash={last_result.get('task_hash')} mission_hash={last_mission.get('task_hash')} type={last_result.get('task_type')} finding_id={last_result.get('finding', {}).get('finding_id')}")
        if not isinstance(last_result, dict):
            return []

        task_type = last_result.get("task_type")

        if task_type == "DISCOVERY":
            finding = last_result.get("finding", {})
            required_keys = {"finding_id", "description", "evidence", "affected_files", "recommended_action", "verification_strategy", "confidence"}
            if not required_keys.issubset(finding.keys()):
                return []
            if not isinstance(finding.get("confidence"), (int, float)) or finding.get("confidence") < 0.8:
                return []

            # Check strict satisfaction FIRST. If satisfied, do NOT queue an implementation mission.
            if self.is_strictly_satisfied(goal_record, last_mission, last_result):
                return []

            # Route all implementation work to GEMINI — no CLI1 special-casing.
            return [{
                "goal": goal_text,
                "normalized_task": f"Implement finding {finding['finding_id']}: {finding['recommended_action']}",
                "capability_required": "implementation",
                "preferred_agent": "GEMINI",
                "is_heavy": True,
                "requires_write": True,
                "task": {
                    "action": "implement_bounded_improvement",
                    "goal_context": goal_text,
                    "prompt": f"Fix {finding['finding_id']}. Details: {finding.get('description', '')}. Verify via: {finding.get('verification_strategy', '')}",
                    "capability_request": "implementation",
                    "acceptance_criteria": self._extract_acceptance_criteria(goal_text) or {"finding_id": finding["finding_id"], "affected_files": finding["affected_files"]}
                }
            }]

        elif task_type == "IMPLEMENTATION":
            files = last_result.get("changed_files", [])
            files_str = ", ".join(files) if len(files) <= 5 else f"{len(files)} files"
            return [{
                "goal": goal_text,
                "normalized_task": f"Verify implementation in {files_str}",
                "capability_required": "repo verification",
                "preferred_agent": "CLI1",
                "is_heavy": False,
                "requires_write": False,
                "is_heavy": True,
                "task": {
                    "action": "verify_improvement_tests",
                    "goal_context": goal_text,
                    "target_files": files,
                    "capability_request": "repo verification",
                    "acceptance_criteria": self._extract_acceptance_criteria(goal_text)
                }
            }]


        elif task_type == "VERIFICATION":
            ev = last_result.get("acceptance_evidence", {})
            if ev.get("tests_passed") is True:
                # Tests passed for the last increment. Do another discovery to see if we're done or need more increments.
                return [{
                    "goal": goal_text,
                    "normalized_task": "Analyze repo state to identify improvements.",
                    "capability_required": "local repo analysis",
                    "preferred_agent": "GEMINI",
                    "is_heavy": True,
                    "requires_write": False,
                    "task": {
                        "action": "discover_improvement_opportunities",
                        "goal_context": goal_text,
                        "capability_request": "local repo analysis"
                    }
                }]
            else:
                # Tests failed, we should probably stop or repair, but returning [] stops the loop
                return []

        return []

class FounderModeMVP:
    def __init__(self, workspace_dir: str, dispatcher: CourierSafetyDispatcher):
        self.workspace_dir = Path(workspace_dir)
        self.intake = MultiChatGoalIntake(self.workspace_dir)
        self.memory = ExperienceMemory(self.workspace_dir)
        self.planner = FounderModePlanner(self.workspace_dir)
        self.queue = MissionQueue(self.workspace_dir)
        self.dispatcher = dispatcher
        self.stats = {
            "autonomous_steps": 0, "cli1_tasks": 0, "google_tasks": 0, 
            "human_gates": 0, "blockers": 0
        }

    def run_autonomous_loop(self):
        # 1. Take highest priority PENDING goal
        goal = self.intake.pop_next_goal()
        if not goal:
            return

        completed_missions = []
        # 2 & 3. Iterative Replan and Execution Loop
        while True:
            # Replan / decompose based on current state
            pending = [m for m in self.queue.read_all() if m["status"] == "PENDING"]
            if not pending:
                next_missions = self.planner.discover_and_plan(goal, completed_missions)
                if not next_missions:
                    if self.planner.evaluate_success(goal, {"status": "PASS"}, completed_missions):
                        self.intake.mark_satisfied(goal["goal_id"])
                    break
                    
                parent_id = completed_missions[-1]["mission_id"] if completed_missions else None
                for m in next_missions:
                    if parent_id: m["parent_mission_id"] = parent_id
                    m["mission_id"] = str(uuid.uuid4())
                    self.queue.enqueue(m)
                    parent_id = m["mission_id"]

            # Process next mission using Courier dispatcher
            worker_id = "founder_loop_1"
            mission_result = self.dispatcher.process_next_mission(worker_id)
            
            if not mission_result:
                break # Queue somehow empty
                
            status = mission_result.get("status")
            agent_used = mission_result.get("agent_dispatched")
            
            self.stats["autonomous_steps"] += 1
            if agent_used == "CLI1": self.stats["cli1_tasks"] += 1
            if agent_used in ["GEMINI", "GOOGLE", "CODEX"]: self.stats["google_tasks"] += 1
            
            if status == "HUMAN_GATE":
                self.stats["human_gates"] += 1
                self.intake.set_status(goal["goal_id"], "HUMAN_GATE")
                break
                
            if status in ["BLOCKED", "FAIL", "FAILED", "UNKNOWN"]:
                self.stats["blockers"] += 1
                # Record error lesson
                self.memory.record_lesson(
                    goal=goal["goal"], task=mission_result.get("mission", {}).get("normalized_task", ""),
                    result=status, error=mission_result.get("reason", ""), root_cause="Unknown",
                    lesson="Failed execution on this approach.", reusable_pattern="None"
                )
                
                # Fetch blocker evidence if WORKER_UNAVAILABLE
                evidence = None
                if mission_result.get("reason") == "WORKER_UNAVAILABLE":
                    from scripts.worker_availability import WorkerAvailabilityResolver
                    resolver = WorkerAvailabilityResolver()
                    gemini_evidence = resolver.resolve_gemini()
                    evidence = {"worker_evidence": gemini_evidence.to_dict()}
                
                    continue
                from scripts.courier_self_repair import CourierSelfRepair
                repair = CourierSelfRepair(self.workspace_dir)
                res = repair.handle_failure(
                    goal_id=goal["goal_id"],
                    original_goal=goal["goal"],
                    failure=mission_result.get("reason", "Unknown failure")
                )
                if res.get("status") == "REPAIR_QUEUED":
                    continue
                if status == "FAILED":
                    continue
                
                self.intake.set_status(goal["goal_id"], "BLOCKED", blocker_evidence=evidence)
                break
            
            if status in ["VERIFIED", "PASS"]:
                # Record success lesson
                self.memory.record_lesson(
                    goal=goal["goal"], task=mission_result.get("mission", {}).get("normalized_task", ""),
                    result="SUCCESS", error="None", root_cause="None",
                    lesson="Implementation succeeded.", reusable_pattern="Standard execution"
                )
                completed_missions.append(self.queue.get(mission_result["mission_id"]))
                



if __name__ == "__main__":
    import argparse
    import sys
    import os
    from pathlib import Path
    from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
    from scripts.courier_real_worker_adapters import get_real_worker_adapters

    parser = argparse.ArgumentParser(description="Submit a goal to Courier Founder Mode.")
    parser.add_argument("--goal", type=str, required=True, help="Human readable goal description")
    args = parser.parse_args()

    workspace = os.getcwd()
    dispatcher = CourierSafetyDispatcher(workspace)
    adapters = get_real_worker_adapters(Path(workspace))
    for agent, adapter in adapters.items():
        dispatcher.adapter_boundary.register_consumer(agent, adapter)

    mvp = FounderModeMVP(workspace_dir=workspace, dispatcher=dispatcher)
    goal_id = mvp.intake.submit_goal(goal=args.goal, source="CLI")
    print(f"Goal Intaked: {goal_id}")
    print("Starting Autonomous Loop...")
    mvp.run_autonomous_loop()
    print("Done.")
    sys.exit(0)
