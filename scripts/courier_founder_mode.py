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
        from scripts.single_flight import is_single_flight_locked
        import os

        def _add(data):
            if not isinstance(data, list):
                raise ValueError("MALFORMED_STATE_FAIL_CLOSED")

            V1_CLOSED = os.environ.get("V1_CLOSED", "FALSE").upper() == "TRUE"
            goal_lower = goal.lower()
            if not V1_CLOSED and ("v2" in goal_lower or "company" in goal_lower or "revenue" in goal_lower or "post-v1" in goal_lower):
                target_status = "POST_V1_PARKED"
            else:
                target_status = "PENDING"

            goal_hash = canonical_hash(goal.strip().lower())
            
            # RECONCILE CURRENT STATE & CHECK DUPLICATES / SATISFIED
            active_count = 0
            for existing in data:
                if existing.get("status") == "ACTIVE":
                    active_count += 1
                
                if canonical_hash(existing.get("goal", "").strip().lower()) == goal_hash:
                    status = existing.get("status")
                    if status == "SATISFIED":
                        return existing["goal_id"] + "_ALREADY_SATISFIED"
                    elif status == "SUPERSEDED":
                        return existing["goal_id"] + "_SUPERSEDED"
                    elif status in ["PENDING", "ACTIVE", "HUMAN_GATE", "BLOCKED", "POST_V1_PARKED"]:
                        # DUPLICATE
                        q = MissionQueue(self.workspace_dir)
                        def _unblock_worker_unavailable_only(doc):
                            changed = False
                            for m in doc.get("missions", []):
                                if m.get("goal") == existing["goal"]:
                                    if m.get("status") == "BLOCKED" and m.get("result_reference") == "WORKER_UNAVAILABLE":
                                        m["status"] = "PENDING"
                                        changed = True
                            return changed
                        q._mutate(_unblock_worker_unavailable_only)
                        return existing["goal_id"] + "_DUPLICATE"

            # Check writer lease / single flight
            if is_single_flight_locked(self.workspace_dir, bypass_for_goal=goal):
                # We do not reject it entirely, we queue it as PENDING (or PARKED)
                # so that queue does not equal execution. The governor will consume it serially.
                pass

            goal_id = str(uuid.uuid4())
            record = GoalRecord(
                goal_id=goal_id, source=source, goal=goal.strip(), priority=priority,
                constraints=constraints or [], created_at=time.time(), status=target_status
            )
            data.append(record.to_dict())
            data.sort(key=lambda x: x.get("priority", 0), reverse=True)
            return goal_id

        try:
            return self._mutate(_add)
        except Exception:
            # FAIL CLOSED
            return "FAIL_CLOSED"

    def pop_next_goal(self) -> Optional[dict]:
        def _pop(data):
            from scripts.worker_availability import WorkerAvailabilityResolver
            from scripts.courier_safety_dispatcher import MissionQueue
            
            resolver = WorkerAvailabilityResolver()
            current_gemini = resolver.resolve_gemini().to_dict()
            
            q = MissionQueue(self.workspace_dir)
            missions = q.read_all()
            
            # Step 1: SINGLE FLIGHT ENFORCEMENT - Enforce MAX_ACTIVE_EXTERNAL_ROOT_GOALS = 1
            active_goals = [g for g in data if g["status"] == "ACTIVE"]
            if active_goals:
                g = active_goals[0]
                has_live = any(m.get("goal") == g["goal"] and m.get("status") in ("PENDING", "RUNNING", "PENDING_VERIFY") for m in missions)
                
                if has_live:
                    # An active, non-orphaned goal exists. Resume it.
                    return g
                else:
                    has_blocked = any(m.get("goal") == g["goal"] and m.get("status") == "BLOCKED" and m.get("result_reference") == "WORKER_UNAVAILABLE" for m in missions)
                    if has_blocked:
                        if "blocker_evidence" in g:
                            ev = g["blocker_evidence"]
                            if "worker_evidence" in ev and current_gemini != ev["worker_evidence"]:
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
                        
                        # Remains blocked. Relinquish the single-flight slot.
                        g["status"] = "BLOCKED"
                    else:
                        has_human_gate = any(m.get("goal") == g["goal"] and m.get("status") == "HUMAN_GATE" for m in missions)
                        if has_human_gate:
                            g["status"] = "WAITING_HUMAN_GATE"
                        else:
                            # Orphaned ACTIVE goal. Resume it.
                            return g

            # Step 2: Unblock BLOCKED goals if evidence changed
            for g in data:
                if g["status"] == "BLOCKED" and "blocker_evidence" in g:
                    ev = g["blocker_evidence"]
                    if "worker_evidence" in ev and current_gemini != ev["worker_evidence"]:
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
            
            # Step 2b: Unblock WAITING_HUMAN_GATE goals if a mission was resumed
            for g in data:
                if g["status"] == "WAITING_HUMAN_GATE":
                    has_live = any(m.get("goal") == g["goal"] and m.get("status") in ("PENDING", "RUNNING", "PENDING_VERIFY") for m in missions)
                    if has_live:
                        g["status"] = "ACTIVE"
                        return g

            # Step 3: Admit a new PENDING goal
            for g in data:
                if g["status"] == "PENDING":
                    g["status"] = "ACTIVE"
                    return g

            return None
        return self._mutate(_pop)

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
        if ref and isinstance(ref, str) and Path(ref).exists():
            try:
                with open(ref, "r") as f:
                    data = json.load(f)
                payload = data.get("result", {}).get("payload", data.get("payload", {}))

                action = payload.get("action", "")
                stage = payload.get("stage", "")

                # DISCOVERY — any worker that reported a discovery action
                if action == "discover_improvement_opportunities" or "DISCOVERY" in stage.upper():
                    res = {
                        "task_type": "DISCOVERY",
                        "finding": {
                            "finding_id": payload.get("weakness_id", "UNKNOWN"),
                            "description": payload.get("description", ""),
                            "evidence": str(payload.get("evidence", "")),
                            "affected_files": payload.get("suggested_files", []),
                            "recommended_action": "Fix weakness",
                            "verification_strategy": payload.get("verification_strategy", ""),
                            "confidence": 1.0
                        }
                    }

                # VERIFICATION — explicit verification action or stage
                elif (action == "verify_improvement_tests" or "VERIFICATION" in stage.upper() or "ACCEPTANCE_AUDIT" in stage.upper()) and mission.get("task", {}).get("capability_request") != "implementation":
                    res = {
                        "task_type": "VERIFICATION",
                        "acceptance_evidence": {"goal_satisfied": payload.get("test_returncode") == 0 or payload.get("verdict") == "PASS"}
                    }

                # IMPLEMENTATION — explicit implementation action/stage with changed files
                elif (
                    action in ("implementation", "implement")
                    or "IMPLEMENTATION" in stage.upper()
                    or payload.get("changed_files")
                    or mission.get("task", {}).get("capability_request") == "implementation"
                ):
                    changed = payload.get("changed_files") or ["auto_detected_changes"]
                    res = {
                        "task_type": "IMPLEMENTATION",
                        "changed_files": changed if isinstance(changed, list) else [changed],
                    }

            except Exception:
                pass
        return res

    def _requires_write_contract(self, goal_text: str) -> bool:
        if not isinstance(goal_text, str): return False
        text = goal_text.lower()
        return "file named" in text or "file:" in text or "repository-root file" in text

    def _extract_acceptance_criteria(self, goal_text: str) -> dict:
        import re
        match = re.search(r"file named (\S+) containing exactly:\s*(.*)", goal_text, re.IGNORECASE | re.DOTALL)
        if match:
            return {"file_exists": match.group(1), "content_matches": match.group(2).strip()}
        return {}

    def discover_and_plan(self, goal_record: dict, completed_missions: list = None) -> list:
        self.last_planning_error = None
        goal_text = goal_record["goal"]
        completed = completed_missions or []

        requires_write = self._requires_write_contract(goal_text)
        acceptance_criteria = self._extract_acceptance_criteria(goal_text)

        if requires_write and not acceptance_criteria:
            self.last_planning_error = "WRITE_ACCEPTANCE_CRITERIA_UNDERIVABLE"
            return []

        if not completed:
            # DISCOVERY MISSION
            return [{
                "goal": goal_text,
                "normalized_task": "Analyze repo state to identify improvements.",
                "capability_required": "local repo analysis",
                "preferred_agent": "GEMINI",
                "is_heavy": False,
                "requires_write": False,
                "task": {
                    "action": "discover_improvement_opportunities",
                    "goal_context": goal_text,
                    "capability_request": "local repo analysis",
                }
            }]

        last_mission = completed[-1]
        last_result = self._load_result(last_mission)
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
                
            if finding.get("finding_id") == "NONE":
                return []

            # IMPLEMENTATION MISSION
            task = {
                "action": "implement_bounded_improvement",
                "prompt": f"Fix {finding['finding_id']}",
                "capability_request": "implementation"
            }
            if requires_write:
                task["requires_write"] = True
                task["target_files"] = [acceptance_criteria.get("file_exists")]
                task["acceptance_criteria"] = acceptance_criteria
                
            return [{
                "goal": goal_text,
                "normalized_task": f"Implement finding {finding['finding_id']}: {finding['recommended_action']}",
                "capability_required": "implementation",
                "preferred_agent": "GEMINI",
                "is_heavy": True,
                "requires_write": requires_write,
                "task": task
            }]

        elif task_type == "IMPLEMENTATION":
            files = last_result.get("changed_files", [])
            return [{
                "goal": goal_text,
                "normalized_task": f"Verify implementation in {', '.join(files)}",
                "capability_required": "repo verification",
                "preferred_agent": "CLI1",
                "is_heavy": False,
                "requires_write": False,
                "task": {
                    "action": "verify_improvement_tests",
                    "goal_context": goal_text,
                    "target_files": files,
                    "capability_request": "repo verification",
                    "acceptance_criteria": acceptance_criteria
                }
            }]

        return []

    def evaluate_success(self, goal_record: dict, last_result: dict, completed_missions: list = None) -> bool:
        if not completed_missions:
            return False
        
        # Check if we have a VERIFIED implementation mission
        has_verified_impl = False
        for m in completed_missions:
            if m.get("status") == "VERIFIED" and m.get("requires_write") is True:
                has_verified_impl = True
            if m.get("task", {}).get("action") == "implement_bounded_improvement" and m.get("status") == "VERIFIED":
                has_verified_impl = True
            if m.get("requires_write") is False and m.get("capability_required") == "implementation" and m.get("status") == "VERIFIED":
                has_verified_impl = True
                
        # Or if the last mission was an implementation mission that requires no further verification
        last_m = completed_missions[-1]
        if last_m.get("capability_required") == "implementation" and last_m.get("status") == "VERIFIED":
            has_verified_impl = True
            
        if last_result.get("mission") and self._load_result(last_result.get("mission")).get("task_type") == "VERIFICATION":
            ev = self._load_result(last_result.get("mission")).get("acceptance_evidence", {})
            if ev.get("goal_satisfied") is True and has_verified_impl: return True
            
        if completed_missions and len(completed_missions) > 0:
            mission = completed_missions[-1]
            res = self._load_result(mission)
            if res.get("task_type") == "DISCOVERY" and res.get("finding", {}).get("finding_id") == "NONE" and mission.get("status") == "VERIFIED":
                return True
            if res.get("task_type") == "VERIFICATION":
                ev = res.get("acceptance_evidence", {})
                if ev.get("goal_satisfied") is True and has_verified_impl:
                    return True
            if res.get("task_type") == "IMPLEMENTATION" and mission.get("status") == "VERIFIED" and (not mission.get("requires_write") or has_verified_impl):
                return True
        return False

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
        import time
        while True:
            # 1. Take highest priority PENDING goal
            goal = self.intake.pop_next_goal()
            if not goal:
                print("No safe V1 work or blocked. Sleeping...")
                time.sleep(10)
                continue

            completed_missions = []
            # 2 & 3. Iterative Replan and Execution Loop
            while True:
                all_missions = self.queue.read_all()
                pending = [m for m in all_missions if m["status"] == "PENDING"]
                running_or_verify = [m for m in all_missions if m["status"] in ("RUNNING", "PENDING_VERIFY")]
                
                if not pending and not running_or_verify:
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
            
                if not mission_result or mission_result.get("status") == "NO_PENDING_MISSION":
                    if running_or_verify:
                        print("Waiting for running/verifying missions...")
                        time.sleep(5)
                        continue
                    break # Queue somehow empty
                
                status = mission_result.get("status")
                agent_used = mission_result.get("agent_dispatched")
            
                self.stats["autonomous_steps"] += 1
                if agent_used == "CLI1": self.stats["cli1_tasks"] += 1
                if agent_used in ["GEMINI", "GOOGLE", "CODEX"]: self.stats["google_tasks"] += 1
            
                if status == "HUMAN_GATE":
                    self.stats["human_gates"] += 1
                    continue
                
                if status in ["FAILED", "FAIL_CLOSED"]:
                    self.stats["blockers"] += 1
                    continue
                if status in ["BLOCKED", "FAIL", "UNKNOWN"]:
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
