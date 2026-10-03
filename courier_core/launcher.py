import sys
import subprocess
import os
import urllib.request
import threading
from pathlib import Path
from typing import Tuple, Optional

class LauncherError(Exception):
    pass

class StartupTimeoutError(LauncherError):
    """Raised when the controller fails to complete the startup handshake within the time bound."""
    def __init__(self, message: str, stderr_output: str = ""):
        super().__init__(message)
        self.stderr_output = stderr_output

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
                    raise LauncherError(f"Process exited prematurely with code {self._proc.returncode}. Stderr: {stderr_content}")
                raise LauncherError(f"Failed to receive port. Output: {port_str!r}. Stderr: {stderr_content}")
                
            port = int(port_str)
            
            # 3. Token available
            token_path = self.home / "run" / "controller.token"
            if not token_path.exists():
                raise LauncherError("Token file not found after port was printed.")
            token = token_path.read_text(encoding="utf-8").strip()
            if not token:
                raise LauncherError("Token file is empty.")
                
            # 4. Authenticated health
            # Note: Because port is bound by the socket before printing, the kernel
            # is already enqueuing connections. urlopen will block until the thread calls accept(),
            # without generating a ConnectionRefusedError. No arbitrary time.sleep() retry loop is needed!
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
                
            # 5. READY
            return port, token
            
        finally:
            timer.cancel()
            if timed_out[0] or self._proc.poll() is not None:
                self.stop()

    def stop(self) -> None:
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None

