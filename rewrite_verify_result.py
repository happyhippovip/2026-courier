import re

with open("scripts/courier_safety_dispatcher.py", "r") as f:
    content = f.read()

# I will find the bounds of verify_result
start_idx = content.find("    def verify_result(self, worker_id: str, task_hash: str, verification_status: str, result_data: Any = None) -> str:")
if start_idx == -1:
    print("Cannot find verify_result!")
    exit(1)

end_idx = content.find("    def record_checkpoint(", start_idx)

original_method = content[start_idx:end_idx]

new_method = """    def verify_result(self, worker_id: str, task_hash: str, verification_status: str, result_data: Any = None) -> str:
        state = self._inflight.get(task_hash)
        try:
            if not state or state["worker_id"] != worker_id or verification_status != "PASS" or result_data != state["result"]:
                self.last_result_status = "UNKNOWN" if verification_status == "UNKNOWN" else "FAIL"
                return "FAIL_CLOSED"
                
            attempts = 1
            max_attempts = 2
            
            while attempts <= max_attempts:
                if isinstance(result_data, dict):
                    if result_data.get("status") == "HUMAN_GATE" or result_data.get("payload", {}).get("verdict") in {"HUMAN_APPROVAL_REQUIRED", "HUMAN_GATE"}:
                        self.last_result_status = "HUMAN_GATE"
                        return "FAIL_CLOSED"
                    task = state.get("task", {})
                    mission_id = state.get("mission_id", "unknown")

                    if not self.canonical_validate_result(mission_id, task, result_data, state.get("route")):
                        self.last_result_status = "FAIL"
                        return "FAIL_CLOSED"

                    criteria = task.get("acceptance_criteria")
                    if state.get("requires_write") and not criteria:
                        self.last_result_status = "FAIL"
                        return "FAIL_CLOSED"
                        
                    effect_missing = False

                    if criteria:
                        if "file_exists" in criteria:
                            from pathlib import Path
                            import os
                            ws_path = Path(self.workspace_dir).resolve()
                            fpath = (Path(self.workspace_dir) / criteria["file_exists"]).resolve()

                            # V1-V4: Path containment
                            try:
                                fpath.relative_to(ws_path)
                            except ValueError:
                                self.last_result_status = "FAIL"
                                return "FAIL_CLOSED"

                            # V9: Missing effect rejection
                            if not fpath.exists():
                                effect_missing = True

                            post_content = ""
                            if not effect_missing and "content_matches" in criteria:
                                try:
                                    post_content = fpath.read_text(encoding="utf-8").strip()
                                    if post_content != criteria["content_matches"].strip():
                                        effect_missing = True
                                except Exception:
                                    effect_missing = True

                            # V5-V8: Freshness checks
                            prestate = state.get("prestate")
                            if state.get("requires_write"):
                                if prestate is None or type(prestate) is not dict or "exists" not in prestate:
                                    self.last_result_status = "FAIL"
                                    return "FAIL_CLOSED"
                                
                            if prestate is not None:
                                was_present = prestate.get("exists", False)
                                pre_content = prestate.get("content")

                                req_content = criteria.get("content_matches", "").strip()
                                if was_present:
                                    if "content_matches" in criteria:
                                        if pre_content == req_content:
                                            # V6: Stale artifact rejection
                                            self.last_result_status = "FAIL"
                                            return "FAIL_CLOSED"
                                    else:
                                        self.last_result_status = "FAIL"
                                        return "FAIL_CLOSED"
                                        
                        if effect_missing:
                            if state.get("requires_write") and state.get("route") == "GEMINI" and attempts < max_attempts:
                                attempts += 1
                                envelope = TaskEnvelope(
                                    task_hash=task_hash,
                                    worker_id=worker_id,
                                    target_agent=state.get("route"),
                                    capability=task.get("capability_request", "default"),
                                    requires_write=True,
                                    is_heavy=state.get("is_heavy", False),
                                    verification_required=True,
                                    safety_decision="APPROVED_SAFE",
                                    payload=task,
                                    correlation_id=task.get("correlation_id", ""),
                                    native_attempt=attempts,
                                    task_id=task.get("task_id", ""),
                                    mission_id=state.get("mission_id", ""),
                                    requested_model=task.get("requested_model")
                                )
                                try:
                                    new_dispatch = self.adapter_boundary.dispatch(state.get("route"), envelope, self.adapters)
                                    result_data = new_dispatch.get("result")
                                    state["result"] = result_data
                                    continue
                                except Exception:
                                    self.last_result_status = "FAIL"
                                    return "FAIL_CLOSED"
                            else:
                                self.last_result_status = "FAIL"
                                return "FAIL_CLOSED"
                                
                    break

            self.ledger.record_review(review_id=f"rev-{task_hash[:12]}", checkpoint_commit="CANONICAL", diff_hash=task_hash,
                file_hashes={
                    "task_hash": task_hash,
                    "mission_id": mission_id,
                    "worker_id": worker_id,
                    "effect_verified": "True",
                    "freshness_verified": "True",
                    "result_fingerprint": canonical_hash(result_data)
                }, review_result="APPROVED", review_type="TASK_VERIFICATION")
            
            self.last_result_status = "VERIFIED"
            return "VERIFIED_AND_CACHED"
        except Exception as e:
            self.last_result_status = "FAIL"
            return "FAIL_CLOSED"

"""

content = content.replace(original_method, new_method)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(content)
