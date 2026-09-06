with open("scripts/courier_founder_mode.py", "r") as f:
    text = f.read()

text = text.replace(
"""    def reopen_invalidated_blocker(self, goal_id: str) -> bool:
        records = self._read_no_lock()
        for r in records:
            if r["goal_id"] == goal_id and r["status"] in ("BLOCKED", "FAILED", "HUMAN_GATE"):
                r["status"] = "PENDING"
                self._write_no_lock(records)
                return True
        return False""",
"""    def reopen_invalidated_blocker(self, goal_id: str) -> bool:
        def _reopen(data):
            for r in data:
                if r["goal_id"] == goal_id and r["status"] in ("BLOCKED", "FAILED", "HUMAN_GATE"):
                    r["status"] = "PENDING"
                    return True
            return False
        return self._mutate(_reopen)"""
)

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(text)
