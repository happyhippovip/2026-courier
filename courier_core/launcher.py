import sys
import subprocess
import os
import urllib.request
from pathlib import Path
from typing import Tuple, Optional

class LauncherError(Exception):
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
        
        # 1. Process start
        self._proc = subprocess.Popen(
            [sys.executable, "-m", self.core_module, "--port", "0", "--print-port"],
            env=env,
            stdout=subprocess.PIPE,
            text=True
        )
        
        try:
            # 2. Port received (blocks until port is printed by the target process, no arbitrary sleep)
            port_str = ""
            if self._proc.stdout is not None:
                port_str = self._proc.stdout.readline().strip()
                
            if not port_str or not port_str.isdigit():
                if self._proc.poll() is not None:
                    raise LauncherError(f"Process exited prematurely with code {self._proc.returncode}")
                raise LauncherError(f"Failed to receive port. Output: {port_str!r}")
                
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
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    if resp.status != 200:
                        raise LauncherError(f"Health check failed with status {resp.status}")
            except Exception as e:
                raise LauncherError(f"Health check request failed: {e}")
                
            # 5. READY
            return port, token
            
        except Exception as e:
            self.stop()
            raise e

    def stop(self) -> None:
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
