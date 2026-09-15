import sys
path = "scripts/courier_safety_dispatcher.py"
data = open(path).read()
to_find = """    def claim_next(self, worker_id: str, goal: Optional[str] = None) -> Optional[dict[str, Any]]:
        def claim(document: dict[str, Any]) -> Optional[dict[str, Any]]:
            for mission in document["missions"]:
                if mission.get("status") == "PENDING":
                    if goal is not None and mission.get("goal") != goal:
                        continue
                    mission["status"], mission["claimed_by"] = "CLAIMED", worker_id
                    return dict(mission)
            return None
        return self._mutate(claim)"""

to_replace = """    def claim_next(self, worker_id: str, goal: Optional[str] = None) -> Optional[dict[str, Any]]:
        def claim(document: dict[str, Any]) -> Optional[dict[str, Any]]:
            import os
            v1_closed = os.environ.get("V1_CLOSED", "FALSE").upper() == "TRUE"
            
            ranks = {
                "RELEASE_CRITICAL": 0,
                "ACTIVE_ROOT_GOAL_CRITICAL": 1,
                "DEFECT_REMOVAL": 2,
                "AUTONOMY_CRITICAL": 3,
                "SAFE_PRODUCT_DELTA": 4,
                "PROOF_DEBT_WITH_DECISION_VALUE": 5,
                "POST_V1": 6,
                "HUMAN_GATED": 7,
                "DUPLICATE_WASTE": 8
            }
            
            def classify(m):
                r = str(m.get("risk_class", "")).upper()
                if r == "HUMAN_GATED": return "HUMAN_GATED"
                g = (str(m.get("goal", "")) + " " + str(m.get("task", {}).get("action", "")) + " " + str(m.get("normalized_task", ""))).lower()
                if "duplicate" in g or "waste" in g: return "DUPLICATE_WASTE"
                if any(k in g for k in ["v2", "company", "invoice", "revenue", "market", "economic", "post-v1"]): return "POST_V1"
                if "release critical" in g or "release_critical" in g: return "RELEASE_CRITICAL"
                if "v1 critical" in g or "v1-critical" in g or "active root" in g or "root goal" in g: return "ACTIVE_ROOT_GOAL_CRITICAL"
                if "defect" in g or "fix" in g or "bug" in g: return "DEFECT_REMOVAL"
                if "autonomy" in g: return "AUTONOMY_CRITICAL"
                if "proof" in g or "debt" in g: return "PROOF_DEBT_WITH_DECISION_VALUE"
                return "SAFE_PRODUCT_DELTA"

            best_mission = None
            best_rank = 999
            
            for mission in document["missions"]:
                if mission.get("status") == "PENDING":
                    c = classify(mission)
                    if c == "HUMAN_GATED":
                        mission["status"] = "HUMAN_GATE"
                        continue
                    if c == "DUPLICATE_WASTE":
                        mission["status"] = "DEDUPED"
                        continue
                    if c == "POST_V1" and not v1_closed:
                        continue
                        
                    if goal is not None and mission.get("goal") != goal:
                        continue
                        
                    r = ranks.get(c, 99)
                    if r < best_rank:
                        best_rank = r
                        best_mission = mission
                        
            if best_mission:
                best_mission["status"], best_mission["claimed_by"] = "CLAIMED", worker_id
                return dict(best_mission)
            return None
        return self._mutate(claim)"""

if to_find in data:
    data = data.replace(to_find, to_replace)
    open(path, "w").write(data)
    print("PATCH APPLIED")
else:
    print("FAILED TO FIND TARGET")
