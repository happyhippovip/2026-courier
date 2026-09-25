import re

with open("scripts/cannon_motor.py", "r") as f:
    content = f.read()

crash_recovery_code = """
        # --- CRASH/RESUME RECOVERY ---
        if self.m.get("current_task"):
            crashed_tid = self.m["current_task"]
            try:
                _snap = self.queue_snapshot()
                _t = _snap.get("tasks", {}).get(crashed_tid, {})
            except Exception:
                _t = {}
            if _t.get("status") in ("DONE", "VERIFYING"):
                self.m["current_task"] = None
                self._save()
            else:
                self._wq("block", crashed_tid, "--reason", "CRASH_DURING_EXECUTION")
                if crashed_tid not in self.m.setdefault("needs_review", []):
                    self.m["needs_review"].append(crashed_tid)
                self.m["current_task"] = None
                self.m["state"] = "BLOCKED"
                self.m["error"] = f"crash_recovery_blocked:{crashed_tid}"
                self._save()
                if getattr(self, "yolo", None) is not None: self.yolo.end("CRASH_RECOVERY")
                return {"step": "crash_recovery", "task": crashed_tid, "state": "BLOCKED"}
        # -----------------------------
"""

# Insert right after the run_mode limit check, before checking local_fake
target = """        if self.m.get("local_fake") or self.m.get("continuous_canary"):"""

content = content.replace(target, crash_recovery_code + target)

with open("scripts/cannon_motor.py", "w") as f:
    f.write(content)
