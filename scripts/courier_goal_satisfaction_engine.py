import json
import time
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Any

@dataclass
class GoalSatisfactionState:
    root_goal: str
    goal_acceptance_contract: Dict[str, str]
    required_outcomes: List[str]
    verified_effects: List[str]
    open_real_gaps: List[str]
    branch_local_human_gates: List[str]
    blockers: List[str]
    satisfaction_state: str  # CONTINUE_SAFE_WORK, WAIT_BRANCH_LOCAL_GATE, VERIFIED_COMPLETE, QUIESCENT_WAKEABLE
    last_evaluated_at: float

class GoalSatisfactionEngine:
    def __init__(self, workspace_dir: Path):
        self.db_dir = workspace_dir / "events" / "goal_satisfaction"
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db_file = self.db_dir / "state.json"
        
    def _read_all(self) -> Dict[str, dict]:
        if not self.db_file.exists():
            return {}
        try:
            with open(self.db_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}
            
    def _write_all(self, state: Dict[str, dict]):
        with open(self.db_file, "w") as f:
            json.dump(state, f, indent=2)

    def _extract_contract(self, goal: str) -> Dict[str, str]:
        import re
        criteria = {}
        # Simple extraction for demo:
        match = re.search(r"file named (\S+) containing exactly:\s*(.*)", goal, re.IGNORECASE | re.DOTALL)
        if match:
            criteria["file_exists"] = match.group(1).strip()
            criteria["content_matches"] = match.group(2).strip()
        else:
            # Fallback simple extraction
            if "customer contact" in goal.lower():
                criteria["action"] = "customer_contact"
            else:
                criteria["implied"] = "improve_codebase"
        return criteria

    def recompute(self, root_goal: str, all_missions_for_goal: List[Dict[str, Any]]) -> str:
        # Recompute from EFFECT EVIDENCE, not task counts.
        # Effect evidence is in result_reference or result_data for VERIFIED missions.
        # Human gates are in HUMAN_GATE missions.
        
        contract = self._extract_contract(root_goal)
        
        verified_effects = []
        human_gates = []
        blockers = []
        
        for m in all_missions_for_goal:
            if m.get("status") == "VERIFIED":
                if m.get("requires_write"):
                    res_data = m.get("result_data", {})
                    payload = res_data.get("result", {}).get("payload", res_data.get("payload", {}))
                    files = payload.get("changed_files", [])
                    if isinstance(files, str): files = [files]
                    for f in files:
                        verified_effects.append(f"modified_{f}")
                # If there's an explicit physical effect
                if m.get("result_reference") and isinstance(m.get("result_reference"), str):
                    if m["result_reference"].endswith(".json"):
                        verified_effects.append("verified_physical_effect")
            elif m.get("status") == "HUMAN_GATE":
                human_gates.append(m.get("mission_id"))
            elif m.get("status") in ("BLOCKED", "FAILED"):
                blockers.append(m.get("mission_id"))
                
        # Determine gaps
        open_gaps = []
        if "file_exists" in contract:
            f = contract["file_exists"]
            # Check if there is physical evidence of this file
            has_evidence = False
            for eff in verified_effects:
                if f in eff: has_evidence = True
            
            # Additional physical check just to be sure (since the prompt said "NOT from worker PASS")
            if not has_evidence and Path(f).exists():
                has_evidence = True
                verified_effects.append(f"physical_existence_{f}")
                
            if not has_evidence:
                open_gaps.append(f"missing_file_{f}")
                
        if not contract and not verified_effects:
            open_gaps.append("no_verified_improvements")
            
        # Decision logic
        # If acceptance contract is fully evidenced: VERIFIED_COMPLETE
        if not open_gaps and (contract or verified_effects):
            decision = "VERIFIED_COMPLETE"
        # If only one branch is Human-Gated: search for independent safe same-goal work.
        elif open_gaps:
            if human_gates and not blockers: # We have a human gate, but are there independent safe things to do?
                decision = "CONTINUE_SAFE_WORK"
            elif human_gates and blockers:
                decision = "WAIT_BRANCH_LOCAL_GATE"
            else:
                decision = "CONTINUE_SAFE_WORK"
        elif human_gates:
            decision = "WAIT_BRANCH_LOCAL_GATE"
        else:
            decision = "QUIESCENT_WAKEABLE"
            
        state_dict = self._read_all()
        
        # Persist satisfaction across restart. A restart must not reopen a VERIFIED_COMPLETE goal 
        # unless new contradictory authoritative evidence exists.
        existing = state_dict.get(root_goal)
        if existing and existing.get("satisfaction_state") == "VERIFIED_COMPLETE":
            if not open_gaps:
                decision = "VERIFIED_COMPLETE" # stay complete

        new_state = GoalSatisfactionState(
            root_goal=root_goal,
            goal_acceptance_contract=contract,
            required_outcomes=[k for k in contract.keys()],
            verified_effects=verified_effects,
            open_real_gaps=open_gaps,
            branch_local_human_gates=human_gates,
            blockers=blockers,
            satisfaction_state=decision,
            last_evaluated_at=time.time()
        )
        
        state_dict[root_goal] = asdict(new_state)
        self._write_all(state_dict)
        
        return decision

