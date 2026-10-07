from typing import Dict, List, Optional
from scripts.coordination_ledger import CoordinationReducer, MissionStatus, EventType
from scripts.coordination_delivery import NextAction, NextActionType, AgentID

class CoordinationEngine:
    def __init__(self, reducer: CoordinationReducer):
        self.reducer = reducer

    def evaluate_next_action(self, mission_id: str) -> NextAction:
        mission = self.reducer.get_mission(mission_id)
        
        if not mission:
            return NextAction(
                action_type=NextActionType.PREPARE_MISSION,
                reason=f"Mission {mission_id} is unknown. Need to prepare and assign it.",
                mission_id=mission_id
            )
            
        status = mission["status"]
        
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

    def evaluate_dag(self) -> List[NextAction]:
        # P6 DAG logic: evaluate all missions and find what to do next globally
        missions = self.reducer.get_all_missions()
        actions = []
        for mid, m in missions.items():
            # 7. BLOCKED mission does not freeze unrelated DAG work.
            # We evaluate each mission independently based on its dependencies.
            deps_done = True
            for dep in m.get("depends_on", []):
                dep_m = self.reducer.get_mission(dep)
                if not dep_m or dep_m["status"] != MissionStatus.DONE:
                    deps_done = False
                    break
                    
            # 1. Worker A FINAL result unlocks dependent Worker B mission.
            # If all dependencies are DONE, and we are not DONE, evaluate
            if deps_done and m["status"] != MissionStatus.DONE:
                actions.append(self.evaluate_next_action(mid))
                
        return actions

