import re

replacement = '''
    def reconcile_orphans(self) -> None:
        """Self-healing control plane without a secondary supervisor."""
        from scripts.canonical_authority import is_pid_alive
        import json
        import time
        from pathlib import Path
        
        active_leases = {}
        for lock_file in self.lease_manager.locks_dir.glob("*.lease"):
            try:
                with open(lock_file, "r") as f:
                    data = json.load(f)
                active_leases[str(lock_file)] = data
            except Exception:
                pass
                
        # 1. Release dead leases not tied to missions
        for lock_path, data in list(active_leases.items()):
            pid = data.get("owner_pid")
            if pid and not is_pid_alive(pid):
                Path(lock_path).unlink(missing_ok=True)
                del active_leases[lock_path]
                
        # 2. Check all missions
        all_missions = self.mission_queue.read_all()
        for mission in all_missions:
            m_status = mission.get("status")
            if m_status in ("VERIFIED", "FAILED", "BLOCKED", "HUMAN_GATE", "DEDUPED"):
                continue # TERMINAL_CLEANUP already handled effectively by satisfaction engine
                
            task_hash = mission.get("task_hash")
            mission_id = mission["mission_id"]
            
            # Check PROCESS_ALIVE & LEASE_VALID
            held_by_live = False
            for data in active_leases.values():
                if data.get("task_hash") == task_hash:
                    held_by_live = True
                    break
                    
            # Check DURABLE_PROGRESS_AGE
            age = time.time() - mission.get("updated_at", time.time())
            
            if held_by_live and age < 300: # 5 minutes max stall
                classification = "HEALTHY_WAIT"
            elif held_by_live: # Lease held but stalled
                classification = "HEALTHY_WAIT" # Stalled? Let's leave it for now or kill it. 
                # "Do not create a second supervisor architecture", "blind process killing" is forbidden.
                
            if not held_by_live:
                # Bounded recovery: check how many times this mission has been recovered
                recovery_count = mission.get("recovery_count", 0)
                if recovery_count >= 2:
                    self.mission_queue.transition(mission_id, "BLOCKED", claimed_by=None, result_reference="RECOVERY_LOOP_BLOCKER")
                    continue
                
                target_agent = mission.get("preferred_agent", "UNKNOWN").lower()
                result_file = self.workspace_dir / "events" / "task-envelopes" / f"result_{target_agent}_{task_hash}.json"
                
                if not result_file.exists():
                    classification = "SAFE_RESUME_PRE_EFFECT"
                else:
                    try:
                        with open(result_file, "r") as rf:
                            result_data = json.load(rf)
                        payload = result_data.get("payload", {})
                        if payload.get("status") == "COMPLETED" or payload.get("verdict"):
                            classification = "RECONCILE_CONFIRMED_EFFECT"
                        else:
                            classification = "AMBIGUOUS_EFFECT_HOLD"
                    except Exception:
                        classification = "AMBIGUOUS_EFFECT_HOLD"

                # Apply actions based on classification
                if classification == "HEALTHY_WAIT":
                    continue
                elif classification == "SAFE_RESUME_PRE_EFFECT":
                    # Update recovery count
                    m = self.mission_queue._read_mission(mission_id)
                    m["recovery_count"] = m.get("recovery_count", 0) + 1
                    self.mission_queue._write_mission(m)
                    self.mission_queue.transition(mission_id, "PENDING", claimed_by=None)
                elif classification == "RECONCILE_CONFIRMED_EFFECT":
                    self.mission_queue.transition(mission_id, "PENDING_VERIFY", result_reference=str(result_file))
                    prestate_file = self.workspace_dir / "events" / "task-envelopes" / f"prestate_{task_hash}.json"
                    prestate = json.loads(prestate_file.read_text()) if prestate_file.exists() else {}
                    self._inflight[task_hash] = {
                        "prestate": prestate, "is_heavy": mission.get("is_heavy", False),
                        "worker_id": "recovery", "result": result_data, "task": mission.get("task", {}),
                        "mission_id": mission_id,
                        "route": result_data.get("target_agent", target_agent).upper() if result_data.get("target_agent", target_agent) else target_agent,
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
                elif classification == "AMBIGUOUS_EFFECT_HOLD":
                    self.mission_queue.transition(mission_id, "FAILED", claimed_by=None, result_reference="AMBIGUOUS_EFFECT_QUARANTINE")
'''

with open("scripts/courier_safety_dispatcher.py", "r") as f:
    content = f.read()

# Replace existing reconcile_orphans
import re
new_content = re.sub(
    r"    def reconcile_orphans\(self\) -> None:.*?                    self\.mission_queue\.transition\(mission_id, \"FAILED\", result_reference=\"AMBIGUOUS_EFFECT_QUARANTINE\"\)",
    replacement.strip("\n"),
    content,
    flags=re.DOTALL
)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(new_content)
