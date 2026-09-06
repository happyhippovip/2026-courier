with open("scripts/courier_safety_dispatcher.py", "r") as f:
    content = f.read()

# 1. Routing identity fix
content = content.replace(
    '        expected_agent = task.get("preferred_agent") or dispatched_route\n        if expected_agent and res_data.get("target_agent") and res_data.get("target_agent") != expected_agent: return False',
    '        expected_agent = dispatched_route or task.get("preferred_agent")\n        if expected_agent and res_data.get("target_agent") != expected_agent: return False'
)

# 2. Auth fix (minimal)
content = content.replace(
    'if k not in ("context", "files", "strategy", "acceptance_criteria", "description", "summary", "payload"):',
    'if k not in ("context", "files", "strategy", "acceptance_criteria", "description", "summary", "payload", "task_hash", "correlation_id", "mission_id", "task_id", "result", "result_data"):'
)

# 3. Retry loop (complex replace)
import re

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

"""

new_verify_block = r"""                            from pathlib import Path
                            import os
                            ws_path = Path(self.workspace_dir).resolve()
                            fpath = (Path(self.workspace_dir) / criteria["file_exists"]).resolve()

                            try:
                                fpath.relative_to(ws_path)
                            except ValueError:
                                self.last_result_status = "FAIL"
                                return "FAIL_CLOSED"

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

"""

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
                    
                if "file_exists" in criteria:
                    from pathlib import Path
                    import os
                    ws_path = Path\(self\.workspace_dir\)\.resolve\(\)
                    fpath = \(Path\(self\.workspace_dir\) / criteria\["file_exists"\]\)\.resolve\(\)
                    
                    try:
                        fpath\.relative_to\(ws_path\)
                    except ValueError:
                        self\.last_result_status = "FAIL"
                        return "FAIL_CLOSED"
                        
                    if not fpath\.exists\(\):
                        self\.last_result_status = "FAIL"
                        return "FAIL_CLOSED"
                        
                    if "content_matches" in criteria:
                        try:
                            content = fpath\.read_text\(encoding="utf-8"\)\.strip\(\)
                            if content != criteria\["content_matches"\]\.strip\(\):
                                self\.last_result_status = "FAIL"
                                return "FAIL_CLOSED"
                        except Exception:
                            self\.last_result_status = "FAIL"
                            return "FAIL_CLOSED"
"""

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

content = re.sub(old_verify_wrapper, new_verify_wrapper, content)
content = re.sub(old_verify_block, new_verify_block, content)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(content)

