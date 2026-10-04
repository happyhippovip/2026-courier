import os
import tempfile
from pathlib import Path
from courier_worker.host import write_crash_report, ExecutionSpec

def test_crash_report_redacts_token():
    with tempfile.TemporaryDirectory() as td:
        artifact_dir = os.path.join(td, "artifacts")
        # create fake stderr
        stderr_path = os.path.join(td, "stderr.txt")
        with open(stderr_path, "w") as f:
            f.write("Some crash log\nToken is secret_1234567890_token!\n")
            
        spec = ExecutionSpec(
            task_id="t1", attempt=1, dispatch_id="d1", worker_id="w1",
            argv=("python",), timeout_s=10.0, lease_ttl_s=10.0,
            artifact_dir=artifact_dir, heartbeat_s=0.2
        )
        
        # Test redacting
        path = write_crash_report(artifact_dir, spec, "crash", 1, 1.0, stderr_path, redact_string="secret_1234567890_token")
        
        import json
        with open(path) as f:
            report = json.load(f)
            
        assert "secret_1234567890_token" not in report["stderr_tail"], "Token was not redacted from stderr!"
        assert "[REDACTED_TOKEN]" in report["stderr_tail"], "Token placeholder missing!"
        
