import json
import subprocess
import time
import os

class MuseAdapter:
    def __init__(self, cli_path="muse"):
        self.cli_path = cli_path

    def _run_cmd(self, args, timeout=5, input_data=None):
        try:
            kwargs = {
                "capture_output": True,
                "text": True,
                "timeout": timeout
            }
            if input_data:
                kwargs["input"] = input_data
            
            res = subprocess.run([self.cli_path] + args, **kwargs)
            if res.returncode == 0:
                try:
                    return json.loads(res.stdout)
                except json.JSONDecodeError:
                    return {"status": "error", "message": "malformed output"}
            return {"status": "error", "message": "nonzero exit", "code": res.returncode}
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "timeout"}
        except FileNotFoundError:
            return {"status": "error", "message": "not found"}

    def discover(self):
        return self._run_cmd(["discover"])

    def capabilities(self):
        return {"features": ["discover", "capabilities", "execute", "result", "cancel", "health"]}

    def execute(self, payload):
        return self._run_cmd(["execute"], timeout=10, input_data=json.dumps(payload))

    def result(self, execution_id):
        return self._run_cmd(["result", str(execution_id)])

    def cancel(self, execution_id):
        return self._run_cmd(["cancel", str(execution_id)])

    def health(self):
        return self._run_cmd(["health"])
