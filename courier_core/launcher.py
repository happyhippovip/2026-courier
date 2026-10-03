import sys
import subprocess
import os
import urllib.request
import threading
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Tuple, Optional, Any

@dataclass
class StartupFailureReceipt:
    component: str
    process_identity: Optional[int]
    exit_code: Optional[int]
    stage: str
    logs: str
    evidence_path: str
    recoverability: bool

class LauncherError(Exception):
    def __init__(self, message: str, receipt: Optional[StartupFailureReceipt] = None, stderr_output: str = ""):
        super().__init__(message)
        self.receipt = receipt
        self.stderr_output = stderr_output

class StartupTimeoutError(LauncherError):
    """Raised when the controller fails to complete the startup handshake within the time bound."""
    pass

class Launcher:
    """Deterministic startup handshake for Courier V1 Core."""
    
    def __init__(self, home: str, core_module: str = "courier_core.serve"):
        self.home = Path(home).resolve()
        self.core_module = core_module
        self._proc: Optional[subprocess.Popen] = None
        
    def start(self, timeout_s: float = 10.0) -> Tuple[int, str]:
        """
        Executes the deterministic handshake:
        1. process start
        2. port/url received
        3. token available
        4. authenticated health
        5. READY
        
        Returns:
            Tuple[int, str]: The bound port and the controller token.
        """
        env = os.environ.copy()
        env["COURIER_HOME"] = str(self.home)
        
        stage = "process_start"
        
        # 1. Process start
        self._proc = subprocess.Popen(
            [sys.executable, "-m", self.core_module, "--port", "0", "--print-port"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        timed_out = [False]
        def on_timeout():
            timed_out[0] = True
            if self._proc:
                self._proc.kill()
                
        timer = threading.Timer(timeout_s, on_timeout)
        timer.start()
        
        try:
            stage = "port_binding"
            # 2. Port received (blocks until port is printed by the target process, no arbitrary sleep)
            port_str = ""
            if self._proc.stdout is not None:
                port_str = self._proc.stdout.readline().strip()
                
            if timed_out[0]:
                stderr_content = self._proc.stderr.read() if self._proc.stderr else ""
                raise StartupTimeoutError(
                    f"Startup handshake timed out after {timeout_s}s waiting for port binding.",
                    stderr_output=stderr_content
                )
                
            if not port_str or not port_str.isdigit():
                stderr_content = self._proc.stderr.read() if self._proc.stderr else ""
                if self._proc.poll() is not None:
                    raise LauncherError(f"Process exited prematurely with code {self._proc.returncode}. Stderr: {stderr_content}", stderr_output=stderr_content)
                raise LauncherError(f"Failed to receive port. Output: {port_str!r}. Stderr: {stderr_content}", stderr_output=stderr_content)
                
            port = int(port_str)
            
            stage = "token_available"
            # 3. Token available
            token_path = self.home / "run" / "controller.token"
            if not token_path.exists():
                raise LauncherError("Token file not found after port was printed.")
            token = token_path.read_text(encoding="utf-8").strip()
            if not token:
                raise LauncherError("Token file is empty.")
                
            stage = "authenticated_health"
            # 4. Authenticated health
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/v1/health",
                headers={"X-Courier-Token": token}
            )
            try:
                # Use remaining time for the health check
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    if resp.status != 200:
                        raise LauncherError(f"Health check failed with status {resp.status}")
            except urllib.error.URLError as e:
                if isinstance(e.reason, TimeoutError) or "timed out" in str(e).lower() or timed_out[0]:
                    stderr_content = self._proc.stderr.read() if self._proc.stderr else ""
                    raise StartupTimeoutError(f"Health check timed out after {timeout_s}s.", stderr_output=stderr_content)
                raise LauncherError(f"Health check request failed: {e}")
            except Exception as e:
                raise LauncherError(f"Health check request failed: {e}")
                
            stage = "READY"
            return port, token
            
        except Exception as e:
            # Generate StartupFailureReceipt
            stderr_content = getattr(e, "stderr_output", "")
            if not stderr_content and self._proc and self._proc.stderr:
                try:
                    stderr_content = self._proc.stderr.read()
                except Exception:
                    pass
                    
            exit_code = self._proc.poll() if self._proc else None
            recoverability = isinstance(e, StartupTimeoutError)
            evidence_path = str(self.home / "run" / f"startup_failure_{int(time.time())}.json")
            
            receipt = StartupFailureReceipt(
                component="controller",
                process_identity=self._proc.pid if self._proc else None,
                exit_code=exit_code,
                stage=stage,
                logs=stderr_content,
                evidence_path=evidence_path,
                recoverability=recoverability
            )
            
            os.makedirs(os.path.dirname(evidence_path), exist_ok=True)
            with open(evidence_path, "w", encoding="utf-8") as f:
                json.dump(asdict(receipt), f, indent=2)
                
            if isinstance(e, LauncherError):
                e.receipt = receipt
                
            self.stop()
            raise e
        finally:
            timer.cancel()
            if timed_out[0] or (self._proc and self._proc.poll() is not None):
                self.stop()

    def stop(self) -> None:
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
