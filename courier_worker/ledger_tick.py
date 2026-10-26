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
no token, path or bridge output. It is a status file, not a queue. A failed
status write is logged and counted in ``status_write_failures``.

Turn-boundary auto-continuation: when a provider/agent round ends, the worker
calls :meth:`LedgerTick.request_continuation`. With open work it marks at most
one pending continuation (PENDING_AUTO_CONTINUATION, max 1); further requests
before it is consumed coalesce into it. The next tick then starts a pass
without waiting for ``min_interval_s`` (park and host pressure still apply).
Without open work nothing is marked, so no wake-up happens.
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
# request_continuation() results
CONT_REQUESTED = "requested"
CONT_COALESCED = "coalesced"
CONT_NO_OPEN_WORK = "no-open-work"


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
                 repo_root: Optional[Path] = None,
                 open_work_probe: Optional[Callable[[], bool]] = None):
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
        self._open_work = open_work_probe or self._default_open_work
        self.pending_continuation = False   # PENDING_AUTO_CONTINUATION, at most one
        self.continuation_wakeups = 0
        self.continuations_coalesced = 0
        self.status_write_failures = 0

    def _default_open_work(self) -> bool:
        try:
            from courier_worker.queue_feed import has_open_work
            return bool(has_open_work(self.home))
        except Exception as exc:  # fail closed: unknown work state means no wake-up
            self._log(f"courier_worker.ledger_tick: open-work probe failed ({exc.__class__.__name__})")
            return False

    def request_continuation(self) -> str:
        """Turn ended: mark one pending continuation if work is open (coalescing)."""
        if self.pending_continuation:
            self.continuations_coalesced += 1
            return CONT_COALESCED
        if not self._open_work():
            return CONT_NO_OPEN_WORK
        self.pending_continuation = True
        return CONT_REQUESTED

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
            home = Path(self.home)
            if (home.is_symlink() or home.parent.is_symlink() or home.parent.parent.is_symlink()
                    or path.is_symlink() or path.parent.is_symlink()):
                raise OSError(f"{path}: refusing to follow a symlink")
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(record, fh, sort_keys=True)
            os.replace(tmp, path)
        except OSError as exc:
            self.status_write_failures += 1
            self._log(f"courier_worker.ledger_tick: status write failed ({exc.__class__.__name__}); "
                      f"status_write_failures={self.status_write_failures}")
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return outcome

    def _feed_queue(self) -> None:
        """Opt-in: move queue workkeys into the ledger before the bridge pass."""
        try:
            from courier_worker.queue_feed import feed_once
            report = feed_once(self.home, self.agent_id, self.host_id)
            if report.get("outcome") == "fed":
                self._log(f"courier_worker.ledger_tick: queue feed {json.dumps(report, sort_keys=True)}")
        except Exception as exc:  # never break the worker loop
            self._log(f"courier_worker.ledger_tick: queue feed failed ({exc.__class__.__name__})")

    def __call__(self) -> str:
        if self.parked:
            return SKIPPED_PARKED
        now = self._clock()
        if (not self.pending_continuation and self._last_start is not None
                and now - self._last_start < self.min_interval_s):
            return SKIPPED_INTERVAL
        if self._probe is not None:
            reason = self._probe()
            if reason is not None:
                return SKIPPED_PRESSURE
        if not (self._repo / "scripts" / "ledger_v1_bridge.py").is_file():
            return self._park("bridge-missing")
        self._last_start = now
        self.passes += 1
        if self.pending_continuation:
            self.pending_continuation = False
            self.continuation_wakeups += 1
        self._feed_queue()
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
