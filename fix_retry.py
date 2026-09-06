import re

with open("scripts/courier_safety_dispatcher.py", "r") as f:
    content = f.read()

old_verify_wrapper = r"""    def verify_result\(self, worker_id: str, task_hash: str, verification_status: str, result_data: dict\[str, Any\]\) -> str:
        state = self\._inflight\.get\(task_hash\)
        try:
            if not state or state\["worker_id"\] != worker_id or verification_status != "PASS" or result_data != state\["result"\]:
                self\.last_result_status = "UNKNOWN" if verification_status == "UNKNOWN" else "FAIL"
                return "FAIL_CLOSED"
            
            task = state\.get\("task", \{\}\)
            requires_write = state\.get\("requires_write"\) or task\.get\("requires_write"\)
            
            if requires_write:
                criteria = task\.get\("acceptance_criteria", \{\}\)
                if not criteria:
                    self\.last_result_status = "FAIL"
                    return "FAIL_CLOSED"
                    
                if "file_exists" in criteria:"""

new_verify_wrapper = r"""    def verify_result(self, worker_id: str, task_hash: str, verification_status: str, result_data: dict[str, Any]) -> str:
        state = self._inflight.get(task_hash)
        try:
            if not state or state["worker_id"] != worker_id or verification_status != "PASS" or result_data != state["result"]:
                self.last_result_status = "UNKNOWN" if verification_status == "UNKNOWN" else "FAIL"
                return "FAIL_CLOSED"
            
            attempts = 1
            max_attempts = 2
            
            while attempts <= max_attempts:
                task = state.get("task", {})
                requires_write = state.get("requires_write") or task.get("requires_write")
                
                effect_missing = False
                if requires_write:
                    criteria = task.get("acceptance_criteria", {})
                    if not criteria:
                        self.last_result_status = "FAIL"
                        return "FAIL_CLOSED"
                        
                    if "file_exists" in criteria:"""

old_verify_block = r"""                        # V5-V8: Freshness checks
                        prestate = state\.get\("prestate"\)
                        if state\.get\("requires_write"\):
                            if prestate is None or type\(prestate\) is not dict or "exists" not in prestate:
                                self\.last_result_status = "FAIL"
                                return "FAIL_CLOSED"
                            
                        if prestate is not None:
                            was_present = prestate\.get\("exists", False\)
                            pre_content = prestate\.get\("content"\)

                            req_content = criteria\.get\("content_matches", ""\)\.strip\(\)
                            if was_present:
                                if "content_matches" in criteria:
                                    if pre_content == req_content:
                                        # V6: Stale artifact rejection \(already matched before execution\)
                                        self\.last_result_status = "FAIL"
                                        return "FAIL_CLOSED"
                                else:
                                    # Just file_exists requested, and it was already there\.
                                    # Stale!
                                    self\.last_result_status = "FAIL"
                                    return "FAIL_CLOSED"

            self\.ledger"""

new_verify_block = r"""                            if not fpath.exists():
                                effect_missing = True
                            
                            post_content = ""
                            if not effect_missing and "content_matches" in criteria:
                                try:
                                    post_content = fpath.read_text(encoding="utf-8").strip()
                                    if post_content != criteria["content_matches"].strip():
                                        effect_missing = True
                                except Exception:
                                    effect_missing = True

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

            self.ledger"""

content = re.sub(old_verify_wrapper, new_verify_wrapper, content)
content = re.sub(old_verify_block, new_verify_block, content)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(content)

