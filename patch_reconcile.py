import json
from pathlib import Path
import re

file_path = Path("/Users/user/Downloads/2026-courier/scripts/courier_safety_dispatcher.py")
content = file_path.read_text()

new_reconcile = """
    def reconcile_orphans(self) -> None:
        \"\"\"Identifies dead lease holders and safely reclaims stranded heavy and writer leases.\"\"\"
        from scripts.canonical_authority import is_pid_alive
        import json
        
        # 1. Read all leases
        active_leases = {}
        for lock_file in self.lease_manager.locks_dir.glob("*.lease"):
            try:
                with open(lock_file, "r") as f:
                    data = json.load(f)
                active_leases[str(lock_file)] = data
            except Exception:
                pass
                
        # 2. Release dead leases not tied to missions
        for lock_path, data in list(active_leases.items()):
            pid = data.get("owner_pid")
            if pid and not is_pid_alive(pid):
                Path(lock_path).unlink(missing_ok=True)
                del active_leases[lock_path]
                
        # 3. Check all live missions
        all_missions = self.mission_queue.read_all()
        for mission in all_missions:
            if mission.get("status") not in ("CLAIMED", "RUNNING", "PENDING_VERIFY"):
                continue
                
            task_hash = mission.get("task_hash")
            mission_id = mission["mission_id"]
            
            # Is it held by a live lease?
            held_by_live = False
            for data in active_leases.values():
                if data.get("task_hash") == task_hash:
                    held_by_live = True
                    break
                    
            if held_by_live:
                continue # LIVE_HOLDER
                
            # Orphaned mission!
            target_agent = mission.get("preferred_agent", "UNKNOWN").lower()
            result_file = self.workspace_dir / "events" / "task-envelopes" / f"result_{target_agent}_{task_hash}.json"
            
            if not result_file.exists():
                # DEAD HOLDER + NO EFFECT
                self.mission_queue.transition(mission_id, "PENDING", claimed_by=None)
            else:
                try:
                    with open(result_file, "r") as rf:
                        result_data = json.load(rf)
                    payload = result_data.get("payload", {})
                    if payload.get("status") == "COMPLETED" or payload.get("verdict"):
                        # DEAD HOLDER + CONFIRMED EFFECT -> Verify/Customs
                        # We must run verify here so it isn't stuck in PENDING_VERIFY
                        self.mission_queue.transition(mission_id, "PENDING_VERIFY", result_reference=str(result_file))
                        
                        # Populate inflight so verify_result works
                        self._inflight[task_hash] = {
                            "worker_id": "recovery",
                            "result": result_data,
                            "task": mission.get("task", {}),
                            "mission_id": mission_id,
                            "route": target_agent,
                            "requires_write": mission.get("task", {}).get("requires_write", False)
                        }
                        try:
                            verified = self.verify_result("recovery", task_hash, "PASS", result_data)
                            if verified == "VERIFIED_AND_CACHED":
                                self.mission_queue.transition(mission_id, "VERIFIED", claimed_by="recovery", verification_reference=task_hash)
                            else:
                                self.mission_queue.transition(mission_id, "FAILED", claimed_by="recovery", result_reference="VERIFICATION_FAIL_CLOSED")
                        except Exception:
                            self.mission_queue.transition(mission_id, "BLOCKED", claimed_by="recovery", result_reference="VERIFY_EXCEPTION")
                    else:
                        # DEAD HOLDER + AMBIGUOUS EFFECT
                        self.mission_queue.transition(mission_id, "FAILED", result_reference="AMBIGUOUS_EFFECT_QUARANTINE")
                except Exception:
                    # DEAD HOLDER + AMBIGUOUS EFFECT
                    self.mission_queue.transition(mission_id, "FAILED", result_reference="AMBIGUOUS_EFFECT_QUARANTINE")
"""

# Replace the old reconcile_orphans
import re
pattern = re.compile(r'    def reconcile_orphans\(self\) -> None:.*?^    def evaluate_routing', re.MULTILINE | re.DOTALL)
new_content = pattern.sub(new_reconcile.strip() + "\n\n    def evaluate_routing", content)

file_path.write_text(new_content)
print("Patched reconcile_orphans")
