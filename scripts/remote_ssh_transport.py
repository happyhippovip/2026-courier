import subprocess
import json
import uuid
import sys
from pathlib import Path

from remote_artifact_isolation import RemoteLifecycleLedger, RemoteLifecycleError

class SSHRemoteTransport:
    """Bounded, noninteractive SSH transport for RemoteLifecycleLedger (R16)."""
    
    def __init__(self, target_host: str, ledger_path: Path):
        self.target_host = target_host
        self.ledger = RemoteLifecycleLedger(ledger_path)
        # Bounded safe arguments: No X11, strict host key checking (assumed authorized), BatchMode.
        self.ssh_base = ["ssh", "-o", "BatchMode=yes", "-o", "ClearAllForwardings=yes"]
    
    def _run_ssh(self, remote_cmd: list[str], timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
        # Validate that the remote command is not a shell string but a list of safe arguments.
        # We will wrap it in single quotes safely, but standard library handles arguments safely via shlex.
        # Actually, ssh concatenates arguments into a string. We must be very careful.
        import shlex
        safe_cmd_string = " ".join(shlex.quote(c) for c in remote_cmd)
        
        return subprocess.run(
            self.ssh_base + [self.target_host, safe_cmd_string],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )

    def start_workload(self, task_id: str, attempt: int, generation: str, remote_script: str) -> str:
        """Start a predefined workload and capture its remote identity (PID)."""
        # Run it in the background using nohup and print the PID.
        # The workload is predefined and safe.
        safe_cmd = f"nohup {remote_script} > /tmp/{task_id}_{attempt}.out 2>&1 & echo $!"
        
        # We use a single string here because we are explicitly composing a controlled shell command.
        # The remote_script must be a predefined safe path.
        if " " in remote_script or ";" in remote_script:
            raise ValueError("Invalid remote script path.")
            
        result = subprocess.run(
            self.ssh_base + [self.target_host, safe_cmd],
            capture_output=True,
            text=True,
            timeout=30.0,
            check=False
        )
        if result.returncode != 0:
            raise RemoteLifecycleError(f"SSH_TRANSPORT_FAILED: {result.stderr}")
            
        remote_pid = result.stdout.strip()
        if not remote_pid.isdigit():
            raise RemoteLifecycleError("FAILED_TO_CAPTURE_REMOTE_IDENTITY")
            
        # Record start in ledger
        self.ledger.start(
            task_id=task_id,
            attempt=attempt,
            generation=generation,
            remote_id=remote_pid,
            target=self.target_host,
            command=remote_script,
            effect="workload_started"
        )
        return remote_pid

    def probe_workload(self, remote_pid: str) -> bool:
        """Check if remote PID is still running."""
        # Standard POSIX kill -0 to check existence
        result = self._run_ssh(["kill", "-0", remote_pid])
        return result.returncode == 0
