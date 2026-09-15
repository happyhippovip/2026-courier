import re
with open("scripts/courier_safety_dispatcher.py", "r") as f:
    content = f.read()

replacement = """
            if held_by_live and age < 300: # 5 minutes max stall
                classification = "HEALTHY_WAIT"
            elif held_by_live: # Lease held but stalled
                classification = "HEALTHY_WAIT" # Stalled? Let's leave it for now or kill it. 
                
            print(f"Self-Healing [Mission {mission_id[:8]}]: PROCESS_ALIVE={held_by_live}, LEASE_VALID={held_by_live}, DURABLE_PROGRESS_AGE={age:.1f}s")
            
            if not held_by_live:
                # Bounded recovery: check how many times this mission has been recovered
                recovery_count = mission.get("recovery_count", 0)
                if recovery_count >= 2:
                    print(f"Self-Healing [Mission {mission_id[:8]}]: Bounded recovery exhausted. Escalating to durable blocker.")
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
                        
                print(f"Self-Healing [Mission {mission_id[:8]}]: EFFECT_STATE resolved -> Classification: {classification}")
"""

new_content = re.sub(
    r"            if held_by_live and age < 300:.*?                    except Exception:\n\s*classification = \"AMBIGUOUS_EFFECT_HOLD\"",
    replacement.strip("\n"),
    content,
    flags=re.DOTALL
)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(new_content)
