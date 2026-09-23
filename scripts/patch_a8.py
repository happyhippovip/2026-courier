import json
from pathlib import Path

motor_path = Path("scripts/cannon_motor.py")
content = motor_path.read_text()
if "current_result_binding_rejected" not in content:
    content = content.replace(
        '''        completed = self._wq("complete", task_id, "--result-json",
                 json.dumps({"result_id": result_id}),
                 "--stage", "ACCEPTED")''',
        '''        try:
            artifact = self.results_dir / (task_id + ".result.json")
            if not artifact.exists():
                raise MotorError("ARTIFACT_MISSING")
            receipt = json.loads(artifact.read_text(encoding="utf-8"))
            if (receipt.get("task_id") != task_id
                    or receipt.get("result_id") != result_id
                    or receipt.get("outcome") != "ok"):
                raise MotorError("ARTIFACT_MISMATCH")
        except (OSError, ValueError, MotorError) as exc:
            self._wq("block", task_id, "--reason", "INVALID_RESULT_BINDING")
            self.m["needs_review"].append(task_id)
            self.m["state"] = "BLOCKED"
            self.m["error"] = str(exc)
            self.m["current_task"] = None
            self._save()
            return {"step": "error", "error": str(exc)}

        completed = self._wq("complete", task_id, "--result-json",
                 json.dumps({"result_id": result_id}),
                 "--stage", "ACCEPTED")'''
    )
    motor_path.write_text(content)
