import re

with open('scripts/cannon_motor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Rename _admit_local_fake to _admit_next_task and update logic
old_admit = '''    def _admit_local_fake(self):
        """One explicit local fake task, never a preallocated limit-sized list.

        Reuse the canonical queue. A previous admission must be durably DONE
        with its matching artifact before a new identity can be admitted.
        """
        snap = self.queue_snapshot()
        if any(t.get("status") in ("CLAIMED", "RUNNING", "VERIFYING")
               for t in snap["tasks"].values()):
            raise MotorError("unfinished_task_requires_review")
        if any(t.get("status") != "DONE" for t in snap["tasks"].values()):
            return  # existing work (including ambiguity) must not be replaced
        last = self.m.get("last_result")
        if self.m.get("started_count", 0):
            if not last or snap["tasks"].get(last["task"], {}).get("status") != "DONE":
                raise MotorError("previous_result_not_reconciled")
            artifact = self.results_dir / (last["task"] + ".result.json")
            receipt = json.loads(artifact.read_text(encoding="utf-8"))
            if (receipt.get("task_id") != last["task"]
                    or receipt.get("result_id") != last["result_id"]
                    or receipt.get("outcome") != "ok"):
                raise MotorError("previous_result_not_verified")
        if self.m.get("pause_requested") or self.m.get("stop_requested"):
            return
        package = "local-fake-" + self.m["run_id"]
        task_id = package + "-" + str(self.m["started_count"] + 1)
        self._wq("init", package)
        self._wq("add", json.dumps({
            "task_id": task_id, "package_id": package,
            "description": "Explicit local fake task (no model/provider)",
            "dependencies": [], "read_scopes": [],
            "write_scopes": ["cannon-local-fake"], "status": "READY"}))'''

new_admit = '''    def _admit_next_task(self):
        """One explicit task, never a preallocated limit-sized list.

        Reuse the canonical queue. A previous admission must be durably DONE
        with its matching artifact before a new identity can be admitted.
        """
        snap = self.queue_snapshot()
        if any(t.get("status") in ("CLAIMED", "RUNNING", "VERIFYING")
               for t in snap["tasks"].values()):
            raise MotorError("unfinished_task_requires_review")
        if any(t.get("status") != "DONE" for t in snap["tasks"].values()):
            return  # existing work (including ambiguity) must not be replaced
        last = self.m.get("last_result")
        if self.m.get("started_count", 0):
            if not last or snap["tasks"].get(last["task"], {}).get("status") != "DONE":
                raise MotorError("previous_result_not_reconciled")
            artifact = self.results_dir / (last["task"] + ".result.json")
            receipt = json.loads(artifact.read_text(encoding="utf-8"))
            if (receipt.get("task_id") != last["task"]
                    or receipt.get("result_id") != last["result_id"]
                    or receipt.get("outcome") != "ok"):
                raise MotorError("previous_result_not_verified")
        if self.m.get("pause_requested") or self.m.get("stop_requested"):
            return
            
        is_fake = self.m.get("local_fake", False)
        prefix = "local-fake-" if is_fake else "real-canary-"
        package = prefix + self.m["run_id"]
        task_id = package + "-" + str(self.m["started_count"] + 1)
        self._wq("init", package)
        
        task_data = {
            "task_id": task_id, "package_id": package,
            "description": "Explicit local fake task (no model/provider)" if is_fake else "Explicit real muse canary task",
            "dependencies": [], "read_scopes": [],
            "write_scopes": ["cannon-local-fake"] if is_fake else ["cannon-real-canary"],
            "status": "READY"
        }
        if not is_fake:
            task_data["executor_kind"] = "REAL_MUSE"
            task_data["acceptance"] = "isolated_nonce_canary_v1"
            task_data["provider"] = "meta"
            
        self._wq("add", json.dumps(task_data))'''

if old_admit not in content:
    print("Could not find old admit method")
    exit(1)
content = content.replace(old_admit, new_admit)

# 2. Update run_step logic
old_run_step = '''        if self.m.get("local_fake"):
            # Persisted deadline also covers reopening during the cooldown.
            delay = self.m.get("next_admission_after", 0) - time.time()
            if delay > 0:
                time.sleep(delay)
                self._load()
            if self.m.get("pause_requested") or self.m.get("stop_requested"):
                self.m["state"] = "PAUSED" if self.m.get("pause_requested") else "IDLE"
                self._save()
                return {"step": "controlled_stop", "state": self.state}
            try:
                self._admit_local_fake()
            except (MotorError, OSError, ValueError) as exc:
                self.m["state"] = "ERROR"
                self.m["error"] = str(exc)
                self._save()
                return {"step": "error", "error": str(exc)}'''

new_run_step = '''        # Persisted deadline also covers reopening during the cooldown.
        delay = self.m.get("next_admission_after", 0) - time.time()
        if delay > 0:
            time.sleep(delay)
            self._load()
        if self.m.get("pause_requested") or self.m.get("stop_requested"):
            self.m["state"] = "PAUSED" if self.m.get("pause_requested") else "IDLE"
            self._save()
            return {"step": "controlled_stop", "state": self.state}
        try:
            self._admit_next_task()
        except (MotorError, OSError, ValueError) as exc:
            self.m["state"] = "ERROR"
            self.m["error"] = str(exc)
            self._save()
            return {"step": "error", "error": str(exc)}'''

if old_run_step not in content:
    print("Could not find old run_step block")
    exit(1)
content = content.replace(old_run_step, new_run_step)

with open('scripts/cannon_motor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patch successful!")
