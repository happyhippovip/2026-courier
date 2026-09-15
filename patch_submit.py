import sys
from pathlib import Path
path = "scripts/courier_safety_dispatcher.py"
data = open(path).read()

to_find = """            envelope = TaskEnvelope("""
to_replace = """            # DURABLE RECOVERY BRAIN: Persist prestate for crash reconciliation
            if prestate:
                from scripts.utils import write_json_atomic
                write_json_atomic(self.workspace_dir / "events" / "task-envelopes" / f"prestate_{task_hash}.json", prestate)
            
            envelope = TaskEnvelope("""

data = data.replace(to_find, to_replace)

to_find_rec = """                        # Populate inflight so verify_result works
                        self._inflight[task_hash] = {"""
to_replace_rec = """                        # Populate inflight so verify_result works
                        prestate_file = self.workspace_dir / "events" / "task-envelopes" / f"prestate_{task_hash}.json"
                        prestate = json.loads(prestate_file.read_text()) if prestate_file.exists() else {}
                        self._inflight[task_hash] = {
                            "prestate": prestate,"""

data = data.replace(to_find_rec, to_replace_rec)
open(path, "w").write(data)
