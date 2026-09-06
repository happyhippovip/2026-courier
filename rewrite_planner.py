import re

with open("scripts/courier_founder_mode.py", "r") as f:
    text = f.read()

new_methods = """    def _requires_write_contract(self, goal_text: str) -> bool:
        if not isinstance(goal_text, str): return False
        text = goal_text.lower()
        return "file named" in text or "file:" in text or "repository-root file" in text

    def _extract_acceptance_criteria(self, goal_text: str) -> dict:
        import re
        match = re.search(r"file named (\\S+) containing exactly:\\s*(.*)", goal_text, re.IGNORECASE | re.DOTALL)
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

            # IMPLEMENTATION MISSION
            task = {
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
                "preferred_agent": "GEMINI",
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
            if res.get("task_type") == "VERIFICATION":
                ev = res.get("acceptance_evidence", {})
                if ev.get("goal_satisfied") is True and has_verified_impl:
                    return True
            if res.get("task_type") == "IMPLEMENTATION" and mission.get("status") == "VERIFIED" and (not mission.get("requires_write") or has_verified_impl):
                return True
        return False
"""

def replacer(match):
    return new_methods

text = re.sub(r'    def _extract_acceptance_criteria.*?return False\n', replacer, text, flags=re.DOTALL)

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(text)
