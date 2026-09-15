import subprocess
import json
from courier_admission_control import TaskPacket
from courier_router import WorkerTarget

class GitHubExternalDispatcher:
    def __init__(self, workflow_name: str = "courier_external_worker.yml"):
        self.workflow_name = workflow_name
        
    def dispatch(self, packet: TaskPacket, target: WorkerTarget, branch: str = "main") -> str:
        # Use GitHub CLI to trigger the workflow dispatch
        cmd = [
            "gh", "workflow", "run", self.workflow_name,
            "--ref", branch,
            "-f", f"goal_id={packet.goal_id}",
            "-f", f"task_id={packet.task_id}",
            "-f", f"attempt_id={packet.attempt_id}",
            "-f", f"result_contract={packet.result_contract}",
            "-f", f"dependencies={json.dumps(packet.dependencies)}"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"GitHub workflow dispatch failed: {result.stderr}")
            
        return f"github-actions-dispatch-{packet.task_id}-{packet.attempt_id}"
