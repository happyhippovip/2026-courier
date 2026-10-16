from typing import Dict, List, Optional
from scripts.coordination_ledger import CoordinationReducer, MissionStatus, EventType
from scripts.coordination_delivery import NextAction, NextActionType, AgentID

class CoordinationEngine:
    def __init__(self, reducer: CoordinationReducer):
        self.reducer = reducer

    def resolve_dependencies(self, mission_id: str) -> Dict:
        """Resolve DAG dependencies for a mission.
        
        Returns:
            resolved (bool): True if all upstream dependencies are DONE.
            dependencies (list): List of dependency mission_ids.
            unresolved (list): List of dicts for incomplete dependencies with mission_id and status.
            resolved_evidence (dict): Mapping of dep_id -> evidence_ref for completed dependencies.
        """
        mission = self.reducer.get_mission(mission_id)
        if not mission:
            return {
                "resolved": False,
                "dependencies": [],
                "unresolved": [{"mission_id": mission_id, "status": "NOT_FOUND"}],
                "resolved_evidence": {}
            }
            
        deps = mission.get("depends_on", [])
        if not deps:
            return {
                "resolved": True,
                "dependencies": [],
                "unresolved": [],
                "resolved_evidence": {}
            }
            
        unresolved = []
        resolved_evidence = {}
        for dep in deps:
            dep_m = self.reducer.get_mission(dep)
            if not dep_m:
                unresolved.append({"mission_id": dep, "status": "UNKNOWN"})
            elif dep_m["status"] != MissionStatus.DONE:
                status_val = dep_m["status"].value if isinstance(dep_m["status"], MissionStatus) else str(dep_m["status"])
                unresolved.append({"mission_id": dep, "status": status_val})
            else:
                resolved_evidence[dep] = dep_m.get("evidence_ref") or ""
                
        return {
            "resolved": len(unresolved) == 0,
            "dependencies": list(deps),
            "unresolved": unresolved,
            "resolved_evidence": resolved_evidence
        }

    def evaluate_next_action(self, mission_id: str) -> NextAction:
        mission = self.reducer.get_mission(mission_id)
        
        if not mission:
            return NextAction(
                action_type=NextActionType.PREPARE_MISSION,
                reason=f"Mission {mission_id} is unknown. Need to prepare and assign it.",
                mission_id=mission_id
            )
            
        status = mission["status"]
        
        dep_res = self.resolve_dependencies(mission_id)
        if not dep_res["resolved"] and status != MissionStatus.DONE:
            unresolved_str = ", ".join(f"{u['mission_id']} ({u['status']})" for u in dep_res["unresolved"])
            has_failed_dep = any(u["status"] in ("ERROR", "BLOCKED") for u in dep_res["unresolved"])
            if has_failed_dep:
                return NextAction(
                    action_type=NextActionType.HUMAN_ACTION_REQUIRED,
                    reason=f"Mission {mission_id} is blocked by failed/blocked dependencies: {unresolved_str}.",
                    mission_id=mission_id,
                    target_agent=mission["agent_id"]
                )
            return NextAction(
                action_type=NextActionType.WAIT,
                reason=f"Mission {mission_id} is waiting for upstream dependencies to resolve: {unresolved_str}.",
                mission_id=mission_id,
                target_agent=mission["agent_id"]
            )
        
        if status == MissionStatus.WORKING:
            return NextAction(
                action_type=NextActionType.WAIT,
                reason=f"Mission {mission_id} is currently WORKING. Await PARTIAL or FINAL event.",
                mission_id=mission_id,
                target_agent=mission["agent_id"]
            )
            
        elif status == MissionStatus.DONE:
            return NextAction(
                action_type=NextActionType.INTEGRATE_RESULTS,
                reason=f"Mission {mission_id} is DONE. Ready to integrate results from {mission['evidence_ref']}.",
                mission_id=mission_id,
                target_agent=mission["agent_id"]
            )
            
        elif status == MissionStatus.BLOCKED:
            return NextAction(
                action_type=NextActionType.HUMAN_ACTION_REQUIRED,
                reason=f"Mission {mission_id} is BLOCKED (Blocker: {mission.get('blocker')}). Human intervention required. Evidence: {mission['evidence_ref']}.",
                mission_id=mission_id,
                target_agent=mission["agent_id"]
            )
            
        elif status == MissionStatus.ERROR:
            # 8. ERROR can be reconciled/reassigned safely
            return NextAction(
                action_type=NextActionType.CANCEL_REQUIRED,
                reason=f"Mission {mission_id} failed with ERROR. Need to cancel or reassign.",
                mission_id=mission_id,
                target_agent=mission["agent_id"]
            )
            
        return NextAction(
            action_type=NextActionType.RECONCILE,
            reason=f"Mission {mission_id} is in an unknown state. Reconcile ledger.",
            mission_id=mission_id,
            target_agent=mission["agent_id"]
        )

    def detect_cycles(self) -> List[List[str]]:
        """Detect cyclical dependencies among non-terminal missions.
        
        Returns a list of cycles (each cycle is a list of mission_ids).
        """
        missions = self.reducer.get_all_missions()
        # Only non-DONE missions can cause an active cycle stall
        active_mids = {mid for mid, m in missions.items() if m.get("status") != MissionStatus.DONE}
        
        # Build adjacency graph: mid -> list of non-DONE dependencies
        adj: Dict[str, List[str]] = {}
        for mid in active_mids:
            deps = missions[mid].get("depends_on", [])
            adj[mid] = [d for d in deps if d in active_mids]
            
        visited: Dict[str, int] = {}  # 0 = unvisited, 1 = visiting, 2 = visited
        cycles: List[List[str]] = []
        
        def dfs(node: str, path: List[str]):
            visited[node] = 1
            path.append(node)
            for neighbor in adj.get(node, []):
                if visited.get(neighbor, 0) == 1:
                    # Cycle detected: extract cycle slice
                    idx = path.index(neighbor)
                    cycle = list(path[idx:])
                    cycles.append(cycle)
                elif visited.get(neighbor, 0) == 0:
                    dfs(neighbor, path)
            path.pop()
            visited[node] = 2

        for mid in list(active_mids):
            if visited.get(mid, 0) == 0:
                dfs(mid, [])
                
        return cycles

    def is_dependency_failed(self, mission_id: str) -> bool:
        """Check if any upstream dependency of a mission has failed or is blocked."""
        dep_res = self.resolve_dependencies(mission_id)
        if dep_res["resolved"]:
            return False
        return any(u.get("status") in ("ERROR", "BLOCKED", "CANCELLED") for u in dep_res.get("unresolved", []))

    def evaluate_dag(self) -> List[NextAction]:
        # P6 DAG logic: evaluate all missions and find what to do next globally
        missions = self.reducer.get_all_missions()
        actions = []
        # Deterministic ordering: older missions first (FIFO by created_at), tie-broken by lexical mission_id
        sorted_missions = sorted(
            missions.values(),
            key=lambda m: (m.get("created_at") or "", m.get("mission_id") or "")
        )
        for m in sorted_missions:
            mid = m["mission_id"]
            if m["status"] == MissionStatus.DONE:
                continue
            # 7. BLOCKED mission does not freeze unrelated DAG work.
            # We evaluate each mission independently based on its dependencies.
            dep_res = self.resolve_dependencies(mid)
            # 1. Worker A FINAL result unlocks dependent Worker B mission.
            # If all dependencies are DONE, and we are not DONE, evaluate
            if dep_res["resolved"]:
                actions.append(self.evaluate_next_action(mid))
            elif self.is_dependency_failed(mid):
                # Lock failed dependency explicitly: do not silently swallow it
                actions.append(self.evaluate_next_action(mid))
                
        if not actions and missions:
            # Check for cyclical dependencies stalling the DAG
            cycles = self.detect_cycles()
            if cycles:
                for cycle in cycles:
                    cycle_str = " -> ".join(cycle + [cycle[0]])
                    for mid in cycle:
                        m = missions.get(mid, {})
                        actions.append(NextAction(
                            action_type=NextActionType.DAG_CYCLE_DETECTED,
                            reason=f"Cyclical dependency detected in DAG: {cycle_str}. Mission {mid} is stalled in cycle.",
                            mission_id=mid,
                            target_agent=m.get("agent_id")
                        ))
                return actions

            # Check if all missions are terminal DONE
            all_done = all(m["status"] == MissionStatus.DONE for m in missions.values())
            if all_done:
                actions.append(NextAction(
                    action_type=NextActionType.TRUE_IDLE,
                    reason=f"All {len(missions)} DAG missions are DONE. Queue is fully exhausted.",
                ))

        return actions

    def select_first_ready(self, agent_id: Optional[AgentID] = None) -> Optional[NextAction]:
        """Deterministically choose the first executable READY action in the DAG.

        Returns None if no mission is currently ready or if all are DONE / stalled.
        Excludes TRUE_IDLE, DAG_CYCLE_DETECTED and locked HUMAN_ACTION_REQUIRED meta-actions.
        """
        for action in self.evaluate_dag():
            if action.action_type in (
                NextActionType.TRUE_IDLE,
                NextActionType.DAG_CYCLE_DETECTED,
                NextActionType.HUMAN_ACTION_REQUIRED,
            ):
                continue
            if agent_id is not None and action.target_agent not in (None, agent_id):
                continue
            return action
        return None

    def select_all_ready(self, agent_id: Optional[AgentID] = None) -> List[NextAction]:
        """Deterministically select all executable READY actions in the DAG.

        Allows independent work across different branches to be continued simultaneously
        even when other branches are blocked, failed, or awaiting human intervention.
        Excludes TRUE_IDLE, DAG_CYCLE_DETECTED, and HUMAN_ACTION_REQUIRED meta-actions.
        """
        ready_actions = []
        for action in self.evaluate_dag():
            if action.action_type in (
                NextActionType.TRUE_IDLE,
                NextActionType.DAG_CYCLE_DETECTED,
                NextActionType.HUMAN_ACTION_REQUIRED,
            ):
                continue
            if agent_id is not None and action.target_agent not in (None, agent_id):
                continue
            ready_actions.append(action)
        return ready_actions

    def is_independent_of(self, candidate_mid: str, target_mid: str) -> bool:
        """Check if candidate mission is structurally independent of target mission.

        Returns True if candidate_mid does NOT depend on target_mid directly or transitively,
        and target_mid does NOT depend on candidate_mid.
        """
        missions = self.reducer.get_all_missions()
        if candidate_mid not in missions or target_mid not in missions:
            return True

        if candidate_mid == target_mid:
            return False

        # Check if candidate depends on target (traverse dependencies of candidate)
        visited_upstream = set()
        stack = list(missions[candidate_mid].get("depends_on", []))
        while stack:
            curr = stack.pop()
            if curr == target_mid:
                return False
            if curr not in visited_upstream:
                visited_upstream.add(curr)
                if curr in missions:
                    stack.extend(missions[curr].get("depends_on", []))

        # Check if target depends on candidate (traverse dependencies of target)
        visited_downstream = set()
        stack = list(missions[target_mid].get("depends_on", []))
        while stack:
            curr = stack.pop()
            if curr == candidate_mid:
                return False
            if curr not in visited_downstream:
                visited_downstream.add(curr)
                if curr in missions:
                    stack.extend(missions[curr].get("depends_on", []))

        return True


