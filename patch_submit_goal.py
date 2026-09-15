import json

def patch():
    with open("scripts/courier_founder_mode.py", "r") as f:
        content = f.read()

    new_submit_goal = """    def submit_goal(self, source: str, goal: str, priority: int = 1, constraints: Optional[list] = None) -> str:
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
"""

    import re
    # We replace from "def submit_goal" up to "return self._mutate(_add)"
    pattern = re.compile(r'    def submit_goal\(self, source.*?return self\._mutate\(_add\)', re.DOTALL)
    
    if not pattern.search(content):
        print("Could not find submit_goal!")
        return

    content = pattern.sub(new_submit_goal.strip('\n'), content)

    with open("scripts/courier_founder_mode.py", "w") as f:
        f.write(content)
    print("Patched submit_goal!")

patch()
