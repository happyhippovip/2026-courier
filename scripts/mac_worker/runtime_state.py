"""Small shared persistence, STOP fencing and process-ownership primitives."""
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

CANONICAL_WORKSPACE = "/Users/user/Downloads/2026-courier"
_POPEN_TYPE = subprocess.Popen

_PS_IDENTITY_TIMEOUT_S = 0.25
_CLEANUP_SIGNAL_ROUNDS = 3
_CLEANUP_ROUND_GRACE_S = 2.0


def read_object(path, default=None):
    try:
        value = json.loads(Path(path).read_text())
    except FileNotFoundError:
        return {} if default is None else default
    if not isinstance(value, dict):
        raise ValueError(f"Non-object state: {path}")
    return value


def sync_directory(path):
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def control_lock(wall):
    wall = Path(wall)
    wall.mkdir(parents=True, exist_ok=True)
    with open(wall / "control.lock", "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def _fingerprint(pid, pgid, extra=()):
    material = ":".join([str(int(pid)), str(int(pgid)), *map(str, extra)])
    return hashlib.sha256(material.encode()).hexdigest()


def _pgid_for_pid(pid):
    try:
        return int(os.getpgid(int(pid)))
    except (OSError, ValueError):
        return None


def _linux_start_fields(pid):
    try:
        stat = Path(f"/proc/{int(pid)}/stat").read_text().split()
        comm = Path(f"/proc/{int(pid)}/comm").read_text().strip()
    except OSError:
        return None
    if len(stat) < 22:
        return None
    return stat[21], comm


def _ps_identity(pid, timeout_s=_PS_IDENTITY_TIMEOUT_S):
    try:
        value = subprocess.check_output(
            ["ps", "-p", str(int(pid)), "-o", "pid=,pgid=,lstart=,comm="],
            text=True, timeout=timeout_s, stderr=subprocess.DEVNULL).strip()
        parts = value.split()
        if len(parts) < 8 or int(parts[0]) != int(pid):
            return None
        return {"pid": int(pid), "pgid": int(parts[1]),
                "fingerprint": hashlib.sha256(" ".join(parts[:7]).encode()).hexdigest(),
                "source": "ps"}
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def capture_process_identity(proc):
    """Identity from a Popen we own. Never depends on a later ps discovery."""
    pid = int(proc.pid)
    pgid = _pgid_for_pid(pid)
    if pgid is None:
        return None
    extra = []
    if sys.platform.startswith("linux"):
        fields = _linux_start_fields(pid)
        if fields:
            extra.extend(fields)
    ident = {
        "pid": pid,
        "pgid": pgid,
        "fingerprint": _fingerprint(pid, pgid, extra),
        "captured_at_spawn": True,
        "spawn_recorded_at": time.time(),
        "source": "spawn",
    }
    enriched = _ps_identity(pid)
    if enriched and enriched.get("pgid") == pgid:
        ident["ps_fingerprint"] = enriched["fingerprint"]
        ident["source"] = "spawn+ps"
    return ident


def process_identity(pid):
    pid = int(pid)
    pgid = _pgid_for_pid(pid)
    if pgid is None:
        return None
    extra = []
    if sys.platform.startswith("linux"):
        fields = _linux_start_fields(pid)
        if fields:
            extra.extend(fields)
    ident = {"pid": pid, "pgid": pgid, "fingerprint": _fingerprint(pid, pgid, extra), "source": "os"}
    enriched = _ps_identity(pid)
    if enriched and enriched.get("pgid") == pgid:
        return enriched
    return ident


def fingerprints_match(pid, identity):
    """True when live pid/pgid matches the recorded fingerprint (not whole dict)."""
    if not identity or "fingerprint" not in identity:
        return False
    pgid = _pgid_for_pid(pid)
    if pgid is None or int(identity.get("pgid", -1)) != pgid:
        return False
    extra = []
    if sys.platform.startswith("linux"):
        fields = _linux_start_fields(pid)
        if fields:
            extra.extend(fields)
    if _fingerprint(pid, pgid, extra) == identity.get("fingerprint"):
        return True
    ps_stored = identity.get("ps_fingerprint")
    if ps_stored:
        current = _ps_identity(pid)
        return bool(current and current.get("fingerprint") == ps_stored)
    return False


def identity_matches(pid, identity):
    if not identity or int(identity.get("pid", -1)) != int(pid):
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        pgid = identity.get("pgid")
        if pgid is None:
            return False
        # Recorded leader exited; keep authority to signal the session group.
        if int(identity.get("pid", -1)) == int(pid):
            return True
        return not group_exists(pgid)
    except OSError:
        return False
    return fingerprints_match(pid, identity)


def same_process(pid, identity):
    return identity_matches(pid, identity)


def group_exists(pgid):
    try:
        os.killpg(int(pgid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return _pgroup_has_live_members(pgid)
    return _pgroup_has_live_members(pgid)


def _pgroup_has_live_members(pgid):
    """True when the group still has a non-zombie member (killpg(0) can lie after leader exit)."""
    try:
        out = subprocess.check_output(
            ["ps", "-g", str(int(pgid)), "-o", "stat="],
            text=True,
            timeout=_PS_IDENTITY_TIMEOUT_S,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return False
    except (OSError, subprocess.SubprocessError):
        return True
    for stat in out.split():
        if stat and not stat.startswith("Z"):
            return True
    return False


def _group_is_gone(pgid, leader_pid=None):
    if leader_pid is not None:
        try:
            os.kill(int(leader_pid), 0)
        except ProcessLookupError:
            return not _pgroup_has_live_members(pgid)
    try:
        os.killpg(int(pgid), 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return not _pgroup_has_live_members(pgid)
    return not _pgroup_has_live_members(pgid)


def _owned_unreaped_session(proc):
    if not isinstance(proc, _POPEN_TYPE) or proc.returncode is not None:
        return False
    try:
        return os.getpgid(proc.pid) == proc.pid
    except OSError:
        return False


def _reap_direct(proc, timeout):
    if isinstance(proc, _POPEN_TYPE) and proc.returncode is None:
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            pass
    elif isinstance(proc, _POPEN_TYPE):
        proc.poll()
    else:
        pid = int(getattr(proc, "pid", 0) or 0)
        if pid:
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass
        poll = getattr(proc, "poll", None)
        if callable(poll):
            poll()


def _session_pgid(proc, identity):
    if identity and identity.get("pgid") is not None:
        return int(identity["pgid"])
    pgid = _pgid_for_pid(proc.pid)
    return pgid if pgid is not None else int(proc.pid)


def _authorized(proc, identity):
    if identity is None:
        return _owned_unreaped_session(proc)
    if _session_pgid(proc, identity) != int(identity["pgid"]):
        return False
    if proc.poll() is not None and int(identity.get("pid", -1)) == int(proc.pid):
        return True
    return identity_matches(proc.pid, identity)


def cleanup_group(proc, identity, grace=_CLEANUP_ROUND_GRACE_S):
    """Signal only an authorized session group until it is gone or rounds exhaust."""
    pgid = _session_pgid(proc, identity)
    leader_pid = int(identity.get("pid", proc.pid)) if identity else int(proc.pid)

    def gone():
        return _group_is_gone(pgid, leader_pid)

    if proc.poll() is not None and gone():
        _reap_direct(proc, 0)
        return True
    if not _authorized(proc, identity):
        return False
    for _round in range(_CLEANUP_SIGNAL_ROUNDS):
        if gone():
            _reap_direct(proc, 0)
            return True
        if identity is not None and proc.poll() is not None:
            if not identity_matches(proc.pid, identity) and not _owned_unreaped_session(proc):
                return False
        for sig in (signal.SIGTERM, signal.SIGKILL):
            if gone():
                _reap_direct(proc, 0)
                return True
            try:
                os.killpg(pgid, sig)
            except ProcessLookupError:
                _reap_direct(proc, 0)
                return True
            deadline = time.monotonic() + grace
            while time.monotonic() < deadline:
                _reap_direct(proc, min(0.05, max(0.0, deadline - time.monotonic())))
                if gone():
                    return True
                time.sleep(0.05)
    _reap_direct(proc, 0)
    return gone()


def process_group_stopped(proc, identity):
    pgid = _session_pgid(proc, identity) if identity else _pgid_for_pid(proc.pid)
    if pgid is None:
        return proc.poll() is not None
    leader_pid = int(identity.get("pid", proc.pid)) if identity else int(proc.pid)
    if _group_is_gone(pgid, leader_pid):
        _reap_direct(proc, 0)
        return True
    return proc.poll() is not None and _group_is_gone(pgid, leader_pid)
