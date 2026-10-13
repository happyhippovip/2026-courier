"""Run one ledger bridge pass when the worker is idle.

The worker loop already ticks: take work, run, deliver, wait. When it finds
no work, :class:`LedgerTick` runs ``scripts.ledger_v1_bridge`` once as a
child process. That one-shot pass feeds finished tasks back to the ledger and
posts the next ready mission to the controller. With the tick on, nobody has
to start the bridge by hand between A and B.

It is not a second scheduler. It never loops by itself, never runs while the
worker owns a task, runs at most once per ``min_interval_s``, and stays off
unless the worker is started with ``--ledger-agent-id`` and
``--ledger-host-id``.

Bridge exit codes:

- 0: pass done or nothing to do.
- 75: controller unreachable. Try again on a later tick.
- 2: config or mission failed closed. Park: no further passes until the
  worker restarts.
- anything else, or a launch error: park as well. A broken bridge does not
  get retried in a tight loop.

A pass that exceeds ``timeout_s`` is killed and retried on a later tick. The
bridge is idempotent per ledger event, so a repeated pass posts nothing twice.
Nothing raised here may stop the worker loop.

After each started pass the tick rewrites ``<home>/run/ledger_tick.json``
(pid, pass count, last outcome and exit code, park reason, UTC time). It holds
no token, path or bridge output. It is a status file, not a queue.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

BRIDGE_MODULE = "scripts.ledger_v1_bridge"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MIN_INTERVAL_S = 30.0
DEFAULT_TIMEOUT_S = 60.0
MIN_INTERVAL_BOUNDS = (0.2, 3600.0)
TIMEOUT_BOUNDS = (1.0, 600.0)
EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_RETRY = 75

# outcome labels (also the return value of LedgerTick.__call__)
RAN = "ran"
RETRY = "retry"
PARKED = "parked"
SKIPPED_INTERVAL = "skipped-interval"
SKIPPED_PRESSURE = "skipped-pressure"
SKIPPED_PARKED = "skipped-parked"
TIMED_OUT = "timeout"
STATUS_FILE = ("run", "ledger_tick.json")


class Completed:
    """Exit code of one finished bridge pass (the runner's return value)."""

    def __init__(self, returncode: int):
        self.returncode = returncode


Runner = Callable[[List[str], str, dict, float], Completed]


def _run_bridge(argv: List[str], cwd: str, env: dict, timeout_s: float) -> Completed:
    """Run the bridge to completion. Output is discarded; the bridge keeps its own log."""
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        return Completed(proc.wait(timeout=timeout_s))
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        raise


class LedgerTick:
    """Callable idle hook: at most one bounded bridge pass per call."""

    def __init__(self, home: str, controller: str, agent_id: str, host_id: str,
                 min_interval_s: float = DEFAULT_MIN_INTERVAL_S,
                 timeout_s: float = DEFAULT_TIMEOUT_S,
                 pressure_probe: Optional[Callable[[], Optional[str]]] = None,
                 runner: Optional[Runner] = None,
                 clock: Callable[[], float] = time.monotonic,
                 log: Optional[Callable[[str], None]] = None,
                 repo_root: Optional[Path] = None):
        if not agent_id or not host_id:
            raise ValueError("agent_id and host_id are required")
        lo, hi = MIN_INTERVAL_BOUNDS
        if not lo <= float(min_interval_s) <= hi:
            raise ValueError(f"min_interval_s must be within [{lo}, {hi}]")
        lo, hi = TIMEOUT_BOUNDS
        if not lo <= float(timeout_s) <= hi:
            raise ValueError(f"timeout_s must be within [{lo}, {hi}]")
        self.home = str(home)
        self.controller = controller
        self.agent_id = agent_id
        self.host_id = host_id
        self.min_interval_s = float(min_interval_s)
        self.timeout_s = float(timeout_s)
        self._probe = pressure_probe
        self._runner = runner or _run_bridge
        self._clock = clock
        self._log = log or (lambda line: print(line, file=sys.stderr, flush=True))
        self._repo = Path(repo_root) if repo_root else REPO_ROOT
        self._last_start: Optional[float] = None
        self.parked_reason: Optional[str] = None
        self.passes = 0

    @property
    def parked(self) -> bool:
        return self.parked_reason is not None

    def argv(self) -> List[str]:
        return [sys.executable, "-m", BRIDGE_MODULE,
                "--home", self.home, "--agent-id", self.agent_id,
                "--host-id", self.host_id, "--controller", self.controller]

    def _env(self) -> dict:
        env = dict(os.environ)
        parts = [str(self._repo)] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]
        env["PYTHONPATH"] = os.pathsep.join(parts)
        return env

    def _park(self, reason: str) -> str:
        self.parked_reason = reason
        self._log(f"courier_worker.ledger_tick: parked ({reason}); restart the worker to resume")
        return PARKED

    def status_path(self) -> Path:
        return Path(self.home).joinpath(*STATUS_FILE)

    def _record(self, outcome: str, exit_code: Optional[int]) -> str:
        record = {
            "pid": os.getpid(),
            "passes": self.passes,
            "outcome": outcome,
            "exit_code": exit_code,
            "parked_reason": self.parked_reason,
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        path = self.status_path()
        tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(record, fh, sort_keys=True)
            os.replace(tmp, path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return outcome

    def __call__(self) -> str:
        if self.parked:
            return SKIPPED_PARKED
        now = self._clock()
        if self._last_start is not None and now - self._last_start < self.min_interval_s:
            return SKIPPED_INTERVAL
        if self._probe is not None:
            reason = self._probe()
            if reason is not None:
                return SKIPPED_PRESSURE
        if not (self._repo / "scripts" / "ledger_v1_bridge.py").is_file():
            return self._park("bridge-missing")
        self._last_start = now
        self.passes += 1
        try:
            done = self._runner(self.argv(), str(self._repo), self._env(), self.timeout_s)
        except subprocess.TimeoutExpired:
            self._log(f"courier_worker.ledger_tick: bridge pass exceeded {self.timeout_s:g}s; retry later")
            return self._record(TIMED_OUT, None)
        except OSError as exc:
            return self._record(self._park(f"launch-failed: {exc.__class__.__name__}"), None)
        code = done.returncode
        if code == EXIT_OK:
            return self._record(RAN, code)
        if code == EXIT_RETRY:
            return self._record(RETRY, code)
        if code == EXIT_CONFIG:
            return self._record(self._park("bridge-config"), code)
        return self._record(self._park(f"bridge-exit-{code}"), code)
