#!/usr/bin/env python3
"""Canonical Windows startup/recovery authority for Google Antigravity.

One supervisor process per Windows user session keeps exactly one Antigravity
instance (on the existing Google profile) alive:

- singleton: an OS file lock rejects a second supervisor; the Scheduled Task
  uses MultipleInstancesPolicy=IgnoreNew as a second guard.
- adopt, never duplicate: a running Antigravity main process is adopted, not
  started again; while a start is in its grace period nothing is spawned.
- health driven: main process + language server + a reachable local listener
  in the Antigravity process tree. Ports are discovered live on every check,
  so a changed port is followed instead of treated as a failure.
- bounded recovery: exponential backoff between start attempts and a hard
  restart budget per window; when the budget is spent it waits (GAVE_UP)
  instead of looping.
- non-destructive: never deletes or creates a profile, never touches
  credentials, never opens a browser, and only ever stops the process tree it
  identified as the Antigravity main instance.

Commands:
  supervisor.py run [--once]   supervise (used by the Scheduled Task)
  supervisor.py status [--json] read-only live status
  supervisor.py e2e            one harmless agent request (agent_probe_command)
  supervisor.py install        register the single startup authority
  supervisor.py uninstall [--restore]
"""

from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import re
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

IS_WINDOWS = os.name == "nt"
APP_NAME = "CourierAntigravity"
TASK_NAME = "CourierAntigravitySupervisor"
LOOPBACK = {"127.0.0.1", "::1", "0.0.0.0", "::", "localhost"}

DEFAULT_EXE_CANDIDATES = (
    r"%LOCALAPPDATA%\Programs\Antigravity\Antigravity.exe",
    r"%ProgramFiles%\Antigravity\Antigravity.exe",
    r"%ProgramFiles(x86)%\Antigravity\Antigravity.exe",
)

STATUS_HEALTHY = "HEALTHY"
STATUS_STARTING = "STARTING"
STATUS_UNHEALTHY = "UNHEALTHY"
STATUS_BACKOFF = "BACKOFF"
STATUS_GAVE_UP = "GAVE_UP"
STATUS_CONFIG_ERROR = "CONFIG_ERROR"


# --------------------------------------------------------------------------
# Redaction: nothing that looks like a credential ever reaches a log or stdout.
# --------------------------------------------------------------------------

SECRET_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)((?:password|passwd|secret|token|api[_-]?key|bearer|oauth|private[_-]?key|auth|cookie|session)[\w-]*\s*[:=]\s*)(['\"]?)[^\s'\"&]{4,}"),
    re.compile(r"ya29\.[A-Za-z0-9._-]{10,}"),
    re.compile(r"1//[A-Za-z0-9._-]{10,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
)


def redact(text: object) -> str:
    out = str(text)
    for pat in SECRET_PATTERNS:
        if pat.groups >= 1:
            out = pat.sub(lambda m: (m.group(1) or "") + "[REDACTED]", out)
        else:
            out = pat.sub("[REDACTED]", out)
    return out


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


# --------------------------------------------------------------------------
# Paths & config
# --------------------------------------------------------------------------

def default_home() -> Path:
    override = os.environ.get("COURIER_ANTIGRAVITY_HOME")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / ".courier-antigravity"


def expand(path: str | None) -> str | None:
    if not path:
        return None
    return os.path.expanduser(os.path.expandvars(path))


def norm_path(path: str | None) -> str:
    if not path:
        return ""
    return os.path.normcase(os.path.normpath(path))


@dataclass
class Config:
    exe_path: str | None = None
    # None = Antigravity's default profile (the one already signed in).
    user_data_dir: str | None = None
    extra_args: list[str] = field(default_factory=list)
    language_server_pattern: str = r"language[_-]?server"
    ui_host: str = "127.0.0.1"
    ui_port: int | None = None  # preferred port hint only; live discovery wins
    ui_scheme: str = "http"
    ui_probe_path: str | None = None  # optional HTTP probe on the discovered port
    check_interval_seconds: float = 30
    startup_grace_seconds: float = 120
    unhealthy_checks_before_restart: int = 4
    restart_unhealthy: bool = True
    backoff_initial_seconds: float = 15
    backoff_max_seconds: float = 600
    max_starts_per_window: int = 5
    start_window_seconds: float = 3600
    stop_timeout_seconds: float = 20
    start_minimized: bool = True
    agent_probe_command: list[str] | None = None
    agent_probe_expect: str | None = None
    agent_probe_timeout_seconds: float = 180

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        known = {f for f in cls.__dataclass_fields__}
        unknown = sorted(k for k in data if k not in known and not k.startswith("_"))
        if unknown:
            raise ValueError(f"unknown config keys: {', '.join(unknown)}")
        cfg = cls(**{k: v for k, v in data.items() if k in known})
        cfg.exe_path = expand(cfg.exe_path)
        cfg.user_data_dir = expand(cfg.user_data_dir)
        if cfg.backoff_initial_seconds <= 0 or cfg.backoff_max_seconds < cfg.backoff_initial_seconds:
            raise ValueError("invalid backoff settings")
        if cfg.max_starts_per_window < 1:
            raise ValueError("max_starts_per_window must be >= 1")
        return cfg

    def resolved_exe(self, exists: Callable[[str], bool] = os.path.isfile) -> str | None:
        if self.exe_path:
            return self.exe_path if exists(self.exe_path) else None
        for cand in DEFAULT_EXE_CANDIDATES:
            path = expand(cand)
            if path and "%" not in path and exists(path):
                return path
        return None


def load_config(path: Path) -> Config:
    if not path.exists():
        return Config()
    return Config.from_dict(json.loads(path.read_text(encoding="utf-8")))


# --------------------------------------------------------------------------
# Process model & backend
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ProcInfo:
    pid: int
    ppid: int
    name: str
    exe: str
    cmdline: tuple[str, ...]
    create_time: float


class Backend(Protocol):
    def list_processes(self) -> list[ProcInfo]: ...
    def listening_ports(self, pids: set[int]) -> dict[int, set[int]]: ...
    def spawn(self, argv: list[str], minimized: bool) -> int: ...
    def terminate_tree(self, pid: int, timeout: float) -> None: ...
    def tcp_probe(self, host: str, port: int, timeout: float = 2.0) -> bool: ...
    def http_probe(self, url: str, timeout: float = 5.0) -> bool: ...
    def now(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...


def user_data_dir_of(cmdline: Iterable[str]) -> str | None:
    args = list(cmdline)
    for i, arg in enumerate(args):
        if arg.startswith("--user-data-dir="):
            return arg.split("=", 1)[1].strip('"')
        if arg == "--user-data-dir" and i + 1 < len(args):
            return args[i + 1].strip('"')
    return None


def find_main_instances(procs: list[ProcInfo], exe: str, user_data_dir: str | None,
                        exclude_pattern: str | None = None) -> list[ProcInfo]:
    """Antigravity main processes for our profile, oldest first.

    Electron children (renderer/gpu/utility) carry --type= or have an
    Antigravity parent; they are not separate instances.
    """
    exe_n = norm_path(exe)
    base = os.path.basename(exe_n)
    by_pid = {p.pid: p for p in procs}
    exclude = re.compile(exclude_pattern, re.I) if exclude_pattern else None

    def is_ag(p: ProcInfo) -> bool:
        if p.exe:
            return norm_path(p.exe) == exe_n
        return os.path.normcase(p.name) == base

    mains = []
    for p in procs:
        if not is_ag(p) or any(a.startswith("--type=") for a in p.cmdline):
            continue
        if exclude and exclude.search(p.name or ""):
            continue  # an orphaned helper (e.g. language server) is not an instance
        parent = by_pid.get(p.ppid)
        if parent is not None and parent.pid != p.pid and is_ag(parent):
            continue
        if norm_path(user_data_dir_of(p.cmdline)) != norm_path(user_data_dir):
            continue
        mains.append(p)
    return sorted(mains, key=lambda p: (p.create_time, p.pid))


def descendants(root: int, procs: list[ProcInfo]) -> list[ProcInfo]:
    children: dict[int, list[ProcInfo]] = {}
    by_pid = {}
    for p in procs:
        by_pid[p.pid] = p
        if p.pid != p.ppid:
            children.setdefault(p.ppid, []).append(p)
    out, stack, seen = [], [root], set()
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        if pid in by_pid:
            out.append(by_pid[pid])
        stack.extend(c.pid for c in children.get(pid, []))
    return out


class PsutilBackend:
    """Live backend. psutil is installed into the supervisor's own venv."""

    CREATE_NEW_PROCESS_GROUP = 0x00000200
    DETACHED_PROCESS = 0x00000008
    CREATE_BREAKAWAY_FROM_JOB = 0x01000000
    CREATE_NO_WINDOW = 0x08000000

    def __init__(self) -> None:
        import psutil  # noqa: PLC0415 - optional dependency, only needed live

        self.ps = psutil

    def list_processes(self) -> list[ProcInfo]:
        out = []
        for p in self.ps.process_iter(["pid", "ppid", "name", "exe", "cmdline", "create_time", "status"]):
            info = p.info
            if info.get("status") == self.ps.STATUS_ZOMBIE:
                continue
            out.append(ProcInfo(
                pid=info["pid"], ppid=info.get("ppid") or 0, name=info.get("name") or "",
                exe=info.get("exe") or "", cmdline=tuple(info.get("cmdline") or ()),
                create_time=info.get("create_time") or 0.0,
            ))
        return out

    def listening_ports(self, pids: set[int]) -> dict[int, set[int]]:
        result: dict[int, set[int]] = {}

        def add(pid: int, conn: Any) -> None:
            if conn.status == self.ps.CONN_LISTEN and conn.laddr and conn.laddr.ip in LOOPBACK:
                result.setdefault(pid, set()).add(conn.laddr.port)

        try:
            for conn in self.ps.net_connections(kind="tcp"):
                if conn.pid in pids:
                    add(conn.pid, conn)
        except (self.ps.AccessDenied, OSError):
            for pid in pids:  # per-process view needs no elevation for own processes
                try:
                    for conn in self.ps.Process(pid).net_connections(kind="tcp"):
                        add(pid, conn)
                except (self.ps.Error, OSError):
                    continue
        return result

    def spawn(self, argv: list[str], minimized: bool) -> int: ...
    def terminate_tree(self, pid: int, timeout: float) -> None: ...
    def tcp_probe(self, host: str, port: int, timeout: float = 2.0) -> bool: ...
    def http_probe(self, url: str, timeout: float = 5.0) -> bool: ...
    def now(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...


def user_data_dir_of(cmdline: Iterable[str]) -> str | None:
    args = list(cmdline)
    for i, arg in enumerate(args):
        if arg.startswith("--user-data-dir="):
            return arg.split("=", 1)[1].strip('"')
        if arg == "--user-data-dir" and i + 1 < len(args):
            return args[i + 1].strip('"')
    return None


def find_main_instances(procs: list[ProcInfo], exe: str, user_data_dir: str | None,
                        exclude_pattern: str | None = None) -> list[ProcInfo]:
    """Antigravity main processes for our profile, oldest first.

    Electron children (renderer/gpu/utility) carry --type= or have an
    Antigravity parent; they are not separate instances.
    """
    exe_n = norm_path(exe)
    base = os.path.basename(exe_n)
    by_pid = {p.pid: p for p in procs}
    exclude = re.compile(exclude_pattern, re.I) if exclude_pattern else None

    def is_ag(p: ProcInfo) -> bool:
        if p.exe:
            return norm_path(p.exe) == exe_n
        return os.path.normcase(p.name) == base

    mains = []
    for p in procs:
        if not is_ag(p) or any(a.startswith("--type=") for a in p.cmdline):
            continue
        if exclude and exclude.search(p.name or ""):
            continue  # an orphaned helper (e.g. language server) is not an instance
        parent = by_pid.get(p.ppid)
        if parent is not None and parent.pid != p.pid and is_ag(parent):
            continue
        if norm_path(user_data_dir_of(p.cmdline)) != norm_path(user_data_dir):
            continue
        mains.append(p)
    return sorted(mains, key=lambda p: (p.create_time, p.pid))


def descendants(root: int, procs: list[ProcInfo]) -> list[ProcInfo]:
    children: dict[int, list[ProcInfo]] = {}
    by_pid = {}
    for p in procs:
        by_pid[p.pid] = p
        if p.pid != p.ppid:
            children.setdefault(p.ppid, []).append(p)
    out, stack, seen = [], [root], set()
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        if pid in by_pid:
            out.append(by_pid[pid])
        stack.extend(c.pid for c in children.get(pid, []))
    return out


class PsutilBackend:
    """Live backend. psutil is installed into the supervisor's own venv."""

    CREATE_NEW_PROCESS_GROUP = 0x00000200
    DETACHED_PROCESS = 0x00000008
    CREATE_BREAKAWAY_FROM_JOB = 0x01000000
    CREATE_NO_WINDOW = 0x08000000

    def __init__(self) -> None:
        import psutil  # noqa: PLC0415 - optional dependency, only needed live

        self.ps = psutil

    def list_processes(self) -> list[ProcInfo]:
        out = []
        for p in self.ps.process_iter(["pid", "ppid", "name", "exe", "cmdline", "create_time", "status"]):
            info = p.info
            if info.get("status") == self.ps.STATUS_ZOMBIE:
                continue
            out.append(ProcInfo(
                pid=info["pid"], ppid=info.get("ppid") or 0, name=info.get("name") or "",
                exe=info.get("exe") or "", cmdline=tuple(info.get("cmdline") or ()),
                create_time=info.get("create_time") or 0.0,
            ))
        return out

    def listening_ports(self, pids: set[int]) -> dict[int, set[int]]:
        result: dict[int, set[int]] = {}
        try:
            conns = self.ps.net_connections(kind="tcp")
        except (self.ps.AccessDenied, OSError):
            conns = []
            for pid in pids:
                try:
                    proc_conns = self.ps.Process(pid).net_connections(kind="tcp")
                except (self.ps.Error, OSError):
                    continue
                conns.extend(c._replace(pid=pid) if hasattr(c, "_replace") and not hasattr(c, "pid") else c
                             for c in proc_conns)
                for c in proc_conns:
                    if c.status == self.ps.CONN_LISTEN and c.laddr and c.laddr.ip in LOOPBACK:
                        result.setdefault(pid, set()).add(c.laddr.port)
            return result
        for c in conns:
            if c.pid in pids and c.status == self.ps.CONN_LISTEN and c.laddr and c.laddr.ip in LOOPBACK:
                result.setdefault(c.pid, set()).add(c.laddr.port)
        return result

    def spawn(self, argv: list[str], minimized: bool) -> int:
        kwargs: dict[str, Any] = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL, close_fds=True,
                                      cwd=os.path.dirname(argv[0]) or None)
        if IS_WINDOWS:
            si = subprocess.STARTUPINFO()
            if minimized:
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 7  # SW_SHOWMINNOACTIVE: no focus stealing
            kwargs["startupinfo"] = si
            flags = self.DETACHED_PROCESS | self.CREATE_NEW_PROCESS_GROUP
            try:
                return subprocess.Popen(argv, creationflags=flags | self.CREATE_BREAKAWAY_FROM_JOB, **kwargs).pid
            except OSError:
                return subprocess.Popen(argv, creationflags=flags, **kwargs).pid
        return subprocess.Popen(argv, start_new_session=True, **kwargs).pid

    def terminate_tree(self, pid: int, timeout: float) -> None:
        try:
            root = self.ps.Process(pid)
        except self.ps.NoSuchProcess:
            return
        tree = [root] + root.children(recursive=True)
        if IS_WINDOWS:
            # Polite close first (WM_CLOSE), exactly this tree, no /F.
            subprocess.run(["taskkill", "/PID", str(pid), "/T"], capture_output=True,
                           creationflags=self.CREATE_NO_WINDOW, check=False)
        else:
            for p in tree:
                try:
                    p.terminate()
                except self.ps.NoSuchProcess:
                    pass
        _, alive = self.ps.wait_procs(tree, timeout=timeout)
        for p in alive:
            try:
                p.kill()
            except self.ps.NoSuchProcess:
                pass

    def tcp_probe(self, host: str, port: int, timeout: float = 2.0) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def http_probe(self, url: str, timeout: float = 5.0) -> bool:
        host = urllib.parse.urlparse(url).hostname or ""
        if host not in LOOPBACK:
            return False  # only ever probe the local machine
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  # local self-signed UI certificate
        try:
            with urllib.request.urlopen(url, timeout=timeout, context=ctx) as resp:
                return 200 <= resp.status < 500
        except urllib.error.HTTPError as exc:
            return exc.code < 500
        except (OSError, ValueError):
            return False

    def now(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


# --------------------------------------------------------------------------
# Singleton lock
# --------------------------------------------------------------------------

class SingletonLock:
    """OS-level exclusive lock; released automatically if the process dies."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+")
        try:
            if IS_WINDOWS:
                import msvcrt  # noqa: PLC0415

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl  # noqa: PLC0415

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self._fh = fh
        return True

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            if IS_WINDOWS:
                import msvcrt  # noqa: PLC0415

                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl  # noqa: PLC0415

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None


# --------------------------------------------------------------------------
# State & health
# --------------------------------------------------------------------------

@dataclass
class State:
    status: str = "UNKNOWN"
    main_pid: int | None = None
    main_create_time: float | None = None
    started_at: float | None = None  # when we last spawned (grace anchor)
    start_attempts: list[float] = field(default_factory=list)
    backoff_level: int = 0
    next_attempt_at: float = 0.0
    consecutive_unhealthy: int = 0
    instances: int = 0
    language_server_running: bool = False
    language_server_connected: bool = False
    ui_port: int | None = None
    ui_url: str | None = None
    last_check: float | None = None
    message: str = ""

    @classmethod
    def load(cls, path: Path) -> "State":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            known = cls.__dataclass_fields__
            return cls(**{k: v for k, v in data.items() if k in known})
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)


@dataclass
class Health:
    main: ProcInfo | None
    instances: int
    language_server_running: bool
    language_server_connected: bool
    ui_port: int | None
    ui_url: str | None

    @property
    def healthy(self) -> bool:
        return bool(self.main and self.language_server_running and self.language_server_connected and self.ui_port)


def evaluate(cfg: Config, backend: Backend, procs: list[ProcInfo], mains: list[ProcInfo]) -> Health:
    if not mains:
        return Health(None, 0, False, False, None, None)
    main = mains[0]
    tree = descendants(main.pid, procs)
    pids = {p.pid for p in tree}
    ports = backend.listening_ports(pids)
    ls_re = re.compile(cfg.language_server_pattern, re.I)
    ls_pids = {p.pid for p in tree if ls_re.search(p.name or "") or ls_re.search(os.path.basename(p.exe or ""))}
    ls_ports = sorted(port for pid in ls_pids for port in ports.get(pid, ()))
    ls_connected = any(backend.tcp_probe(cfg.ui_host, port) for port in ls_ports)

    all_ports = sorted({port for s in ports.values() for port in s})
    candidates = ([cfg.ui_port] if cfg.ui_port in all_ports else []) + [p for p in all_ports if p != cfg.ui_port]
    ui_port = ui_url = None
    for port in candidates:
        if not backend.tcp_probe(cfg.ui_host, port):
            continue
        url = f"{cfg.ui_scheme}://{cfg.ui_host}:{port}"
        if cfg.ui_probe_path is not None and not backend.http_probe(url + cfg.ui_probe_path):
            continue
        ui_port, ui_url = port, url
        break
    return Health(main, len(mains), bool(ls_pids), ls_connected, ui_port, ui_url)


# --------------------------------------------------------------------------
# Supervisor
# --------------------------------------------------------------------------

class Supervisor:
    def __init__(self, cfg: Config, backend: Backend, home: Path,
                 logger: logging.Logger | None = None,
                 exists: Callable[[str], bool] = os.path.isfile,
                 dir_exists: Callable[[str], bool] = os.path.isdir) -> None:
        self.cfg = cfg
        self.backend = backend
        self.home = home
        self.state_path = home / "state.json"
        self.log = logger or logging.getLogger(APP_NAME)
        self._exists = exists
        self._dir_exists = dir_exists
        self.state = State.load(self.state_path)

    # -- helpers ---------------------------------------------------------
    def argv(self, exe: str) -> list[str]:
        argv = [exe]
        if self.cfg.user_data_dir:
            argv.append(f"--user-data-dir={self.cfg.user_data_dir}")
        argv.extend(self.cfg.extra_args)
        return argv

    def _budget_left(self, now: float) -> bool:
        window = self.cfg.start_window_seconds
        self.state.start_attempts = [t for t in self.state.start_attempts if now - t < window]
        return len(self.state.start_attempts) < self.cfg.max_starts_per_window

    def _in_grace(self, now: float) -> bool:
        s = self.state.started_at
        return s is not None and 0 <= now - s < self.cfg.startup_grace_seconds

    def _config_error(self) -> str | None:
        exe = self.cfg.resolved_exe(self._exists)
        if not exe:
            return "Antigravity executable not found (set exe_path in config.json)"
        if self.cfg.user_data_dir and not self._dir_exists(self.cfg.user_data_dir):
            # Never create a fresh profile: that would silently log the user out.
            return "configured user_data_dir does not exist; refusing to start with an empty profile"
        return None

    # -- actions ---------------------------------------------------------
    def _attempt_start(self, now: float, reason: str) -> None:
        st = self.state
        err = self._config_error()
        if err:
            st.status, st.message = STATUS_CONFIG_ERROR, err
            self.log.error("config error: %s", err)
            return
        if now < st.next_attempt_at:
            st.status = STATUS_BACKOFF
            st.message = f"{reason}; next start attempt in {int(st.next_attempt_at - now)}s"
            return
        if not self._budget_left(now):
            st.status = STATUS_GAVE_UP
            oldest = min(st.start_attempts)
            st.message = (f"{reason}; start budget ({self.cfg.max_starts_per_window}/"
                          f"{int(self.cfg.start_window_seconds)}s) spent, retry after "
                          f"{int(oldest + self.cfg.start_window_seconds - now)}s")
            self.log.warning(st.message)
            return
        exe = self.cfg.resolved_exe(self._exists)
        assert exe
        argv = self.argv(exe)
        self.log.info("starting Antigravity (%s): %s", reason, " ".join(argv))
        try:
            pid = self.backend.spawn(argv, self.cfg.start_minimized)
        except OSError as exc:
            pid = None
            self.log.error("spawn failed: %s", exc)
        st.start_attempts.append(now)
        delay = min(self.cfg.backoff_initial_seconds * (2 ** st.backoff_level), self.cfg.backoff_max_seconds)
        st.backoff_level += 1
        st.next_attempt_at = now + delay
        st.consecutive_unhealthy = 0
        if pid is None:
            st.status, st.message = STATUS_BACKOFF, f"spawn failed; retry in {int(delay)}s"
            return
        st.started_at = now
        st.main_pid, st.main_create_time = pid, None
        st.status, st.message = STATUS_STARTING, f"started pid {pid} ({reason})"

    def tick(self) -> State:
        now = self.backend.now()
        st = self.state
        st.last_check = now
        exe = self.cfg.resolved_exe(self._exists) or self.cfg.exe_path or ""
        procs = self.backend.list_processes()
        mains = find_main_instances(procs, exe, self.cfg.user_data_dir, self.cfg.language_server_pattern) if exe else []
        health = evaluate(self.cfg, self.backend, procs, mains)
        st.instances = health.instances
        st.language_server_running = health.language_server_running
        st.language_server_connected = health.language_server_connected
        st.ui_port, st.ui_url = health.ui_port, health.ui_url

        if health.main is None:
            # Stale PID from an earlier run: that process is gone (or the PID
            # was reused by something else), so forget it.
            st.main_pid = st.main_create_time = None
            if self._in_grace(now):
                st.status, st.message = STATUS_STARTING, "start in progress; waiting (no duplicate spawn)"
            else:
                self._attempt_start(now, "Antigravity not running")
        else:
            main = health.main
            if st.main_pid != main.pid or st.main_create_time != main.create_time:
                if st.main_pid != main.pid:
                    self.log.info("tracking Antigravity main pid %s", main.pid)
                    if not self._in_grace(now):
                        st.started_at = None  # adopted, not started by us
                st.main_pid, st.main_create_time = main.pid, main.create_time
            if health.instances > 1:
                self.log.warning("%s Antigravity main instances for this profile; tracking oldest pid %s",
                                 health.instances, main.pid)
            if health.healthy:
                if st.status != STATUS_HEALTHY:
                    self.log.info("healthy: pid %s ui %s", main.pid, health.ui_url)
                st.status, st.message = STATUS_HEALTHY, f"ui {health.ui_url}"
                st.consecutive_unhealthy = 0
                st.backoff_level = 0
                st.next_attempt_at = 0.0
                st.started_at = None
            elif self._in_grace(now):
                st.status, st.message = STATUS_STARTING, "process up, waiting for language server/UI"
            else:
                st.consecutive_unhealthy += 1
                missing = [n for n, ok in (("language server", health.language_server_running),
                                           ("language server connection", health.language_server_connected),
                                           ("local UI listener", bool(health.ui_port))) if not ok]
                st.status = STATUS_UNHEALTHY
                st.message = f"missing: {', '.join(missing)} ({st.consecutive_unhealthy} checks)"
                if (self.cfg.restart_unhealthy
                        and st.consecutive_unhealthy >= self.cfg.unhealthy_checks_before_restart):
                    self._restart(now, main)
        st.save(self.state_path)
        return st

    def _restart(self, now: float, main: ProcInfo) -> None:
        """Replace a degraded instance, but only when a new start is allowed.

        A running (if degraded) instance is never stopped when it could not be
        replaced right away: config error, backoff or spent budget keep it.
        """
        st = self.state
        err = self._config_error()
        if err:
            st.status, st.message = STATUS_CONFIG_ERROR, err
            return
        if now < st.next_attempt_at:
            st.message += f"; restart deferred {int(st.next_attempt_at - now)}s (backoff)"
            return
        if not self._budget_left(now):
            st.status = STATUS_GAVE_UP
            st.message += "; restart budget spent, keeping current instance"
            self.log.warning(st.message)
            return
        self.log.warning("restarting unhealthy Antigravity pid %s: %s", main.pid, st.message)
        self.backend.terminate_tree(main.pid, self.cfg.stop_timeout_seconds)
        self._attempt_start(now, "unhealthy restart")

    def run(self, lock: SingletonLock, max_ticks: int | None = None) -> int:
        if not lock.acquire():
            self.log.info("another supervisor already holds the lock; exiting")
            return 0
        try:
            n = 0
            while max_ticks is None or n < max_ticks:
                n += 1
                try:
                    self.tick()
                except Exception as exc:  # keep supervising; never crash-loop
                    self.log.exception("tick failed: %s", exc)
                if max_ticks is None or n < max_ticks:
                    self.backend.sleep(self.cfg.check_interval_seconds)
            return 0
        finally:
            lock.release()


# --------------------------------------------------------------------------
# Agent end-to-end probe
# --------------------------------------------------------------------------

def run_agent_probe(cfg: Config, runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> tuple[bool, str]:
    if not cfg.agent_probe_command:
        return False, "agent_probe_command not configured"
    kwargs: dict[str, Any] = dict(capture_output=True, text=True, timeout=cfg.agent_probe_timeout_seconds, check=False)
    if IS_WINDOWS:
        kwargs["creationflags"] = PsutilBackend.CREATE_NO_WINDOW
    try:
        proc = runner(list(cfg.agent_probe_command), **kwargs)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, redact(f"probe failed: {exc}")
    out = (proc.stdout or "") + (proc.stderr or "")
    ok = proc.returncode == 0 and (not cfg.agent_probe_expect or cfg.agent_probe_expect in out)
    return ok, redact(out.strip()[-400:])


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def setup_logging(home: Path, verbose: bool = False) -> logging.Logger:
    home.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger(APP_NAME)
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fh = logging.handlers.RotatingFileHandler(home / "supervisor.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    fh.addFilter(RedactingFilter())
    log.addHandler(fh)
    if verbose and sys.stderr is not None:
        sh = logging.StreamHandler()
        sh.addFilter(RedactingFilter())
        log.addHandler(sh)
    return log


def status_report(sup: Supervisor) -> dict[str, Any]:
    cfg, backend = sup.cfg, sup.backend
    exe = cfg.resolved_exe(sup._exists) or cfg.exe_path or ""
    procs = backend.list_processes()
    mains = find_main_instances(procs, exe, cfg.user_data_dir, cfg.language_server_pattern) if exe else []
    health = evaluate(cfg, backend, procs, mains)
    return {
        "ANTIGRAVITY_EXE": exe or None,
        "PROFILE": cfg.user_data_dir or "default",
        "ANTIGRAVITY_INSTANCES": health.instances,
        "MAIN_PID": health.main.pid if health.main else None,
        "LANGUAGE_SERVER_RUNNING": health.language_server_running,
        "LANGUAGE_SERVER_CONNECTED": health.language_server_connected,
        "UI_LISTENING": bool(health.ui_port),
        "UI_URL": health.ui_url,
        "HEALTHY": health.healthy,
        "SUPERVISOR_STATUS": sup.state.status,
        "SUPERVISOR_MESSAGE": sup.state.message,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--home", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--once", action="store_true")
    p_run.add_argument("-v", "--verbose", action="store_true")
    p_status = sub.add_parser("status")
    p_status.add_argument("--json", action="store_true")
    p_status.add_argument("--e2e", action="store_true", help="also run one harmless agent request")
    sub.add_parser("e2e")
    p_inst = sub.add_parser("install")
    p_inst.add_argument("--keep-duplicates", action="store_true", help="report, but do not disable, other Antigravity launchers")
    p_inst.add_argument("--no-start", action="store_true")
    p_un = sub.add_parser("uninstall")
    p_un.add_argument("--restore", action="store_true", help="re-enable launchers disabled by install")
    args = parser.parse_args(argv)
    home = args.home or default_home()

    if args.cmd in ("install", "uninstall"):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import installer  # noqa: PLC0415

        if args.cmd == "install":
            return installer.install(home, disable_duplicates=not args.keep_duplicates, start=not args.no_start)
        return installer.uninstall(home, restore=args.restore)

    cfg = load_config(home / "config.json")
    log = setup_logging(home, verbose=getattr(args, "verbose", False))
    if args.cmd == "e2e":
        ok, detail = run_agent_probe(cfg)
        print(f"AGENT_E2E={'YES' if ok else 'NO'}")
        if detail:
            print(detail)
        return 0 if ok else 1
    sup = Supervisor(cfg, PsutilBackend(), home, log)
    if args.cmd == "status":
        report = status_report(sup)
        if args.e2e:
            ok, _ = run_agent_probe(cfg)
            report["AGENT_E2E"] = ok
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            for k, v in report.items():
                print(f"{k}={v}")
        return 0 if report["HEALTHY"] and report.get("AGENT_E2E", True) else 1
    return sup.run(SingletonLock(home / "supervisor.lock"), max_ticks=1 if args.once else None)


if __name__ == "__main__":
    sys.exit(main())
