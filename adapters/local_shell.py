"""V1 local_shell adapter (lane L4): bounded command execution + independent verification.

Execution contract (for the worker host)::

    run(params, workdir, attempt=1) -> RunResult

``params`` are ``command`` (argv list, executed directly with no shell),
``write`` (evidence file the command is expected to produce inside
``workdir``), ``timeout_s`` (per-attempt bound; expiry kills and reaps the
child, then raises :class:`LocalShellTimeout`, the timeout analog the host
treats like a dead task process), and ``env`` (extra environment entries).
The child does not inherit the worker's environment: it gets the variables in
``INHERITED_ENV`` (OS essentials, no credentials), an empty home folder of its
own, plus ``env``. ``env`` may not name a credential (it is journaled with the
task), a login pointer, nor a path or loader variable (``PROTECTED_ENV``). A
command that would start a provider CLI is refused
(``courier_core.provider_cli_guard``): provider runs go through provider_exec.
``workdir`` is the task sandbox the host owns: the child runs with
``cwd=workdir`` so its relative writes land inside the sandbox, and the
adapter itself writes nowhere (it only reads the declared evidence file back
to hash it). There is deliberately no ``shell=True`` path and no content
pinning at execution time: what the bytes mean is the verifier's job.

Verification contract (for ``courier_core.verification.run_verifier``)::

    verify(task, result, home) -> Verdict-like

``task`` is a ``TaskState``, ``result`` the journaled ``RESULT_READY`` event,
``home`` the file-scope root the caller authorizes reads from. The verifier is
pure and read-only: it never writes, never deletes, and rejected evidence is
left exactly as found (preservation is what lets a human or a retry inspect a
rejection afterwards). Dispatch identity is bound here; attempt staleness
and duplication stay the controller journal's job (fencing + dedupe keys).
Unlike the synthetic adapter there is no declared-content pin: a shell
command's bytes are whatever the command produced, so acceptance means the
evidence is dispatch-bound, well-formed, home-scoped, and self-consistent
(bytes hash to the claimed sha256). Rules, fail closed:

- ``outcome != "success"`` is always rejected; ``retryable`` comes from the
  result payload, defaulting to true only for ``effect_class == "idempotent"``
  (mirrors the controller rule: nothing else becomes retryable by omission).
- when the task names a ``dispatch_id``, the result must name the same one;
  evidence bound to another (or no) dispatch is rejected. The journal fences
  stale dispatches too; this is the verifier's half of that binding.
- success requires a non-empty artifact list of ``{path, sha256}`` dicts.
- every artifact path must be workspace-relative (no absolute, drive, root or
  ``..`` under either Windows or POSIX semantics) and must resolve inside
  ``home``; the file must exist and its bytes must hash to the claimed sha256.
- anything else is rejected with a reason; unexpected internal errors are
  converted to a rejection, never raised (the controller belts this too, but a
  verifier must never depend on its caller for fail-closed behavior).

``verify`` returns a ``courier_core.verification.Verdict`` when that module is
importable (the L2-composed tree) and an identical-shape local verdict
otherwise, so the adapter is unit-testable on this lane alone. The ``verifier``
identity field is always left ``None``: ``run_verifier`` stamps it.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from adapters.synthetic import SHA256_RE, is_safe_name
from courier_core import provider_cli_guard as guard

VERIFIER_VERSION = "1"
# Cost class read by the controller before a task exists. "metered": the argv is free-form (any
# CLI, including a paid provider CLI or an HTTP client with a key in env), so a task must state
# its estimate; only the adapter name is allowlisted, not the command.
COST_CLASS = "metered"

MAX_TIMEOUT_S = 600

FORBIDDEN_COMMAND_FLAGS = frozenset({
    "--dangerously-skip-permissions",
    "--skip-permissions",
    "--no-sandbox",
})


# What a command needs from the host to start and find its tools; nothing that
# authenticates. Everything else in the worker's environment (provider keys, controller
# token, cloud credentials, login pointers) stays out of the child.
INHERITED_ENV = frozenset({
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "TEMP", "TMP", "TMPDIR",
    "LANG", "LANGUAGE", "LC_ALL", "LC_CTYPE", "TZ", "PYTHONIOENCODING", "PYTHONUTF8",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "OS", "USERNAME", "COMPUTERNAME",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432", "PROGRAMDATA", "ALLUSERSPROFILE",
    "COMMONPROGRAMFILES", "COMMONPROGRAMFILES(X86)", "PSMODULEPATH",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "NODE_EXTRA_CA_CERTS",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY", "VIRTUAL_ENV",
})
HOME_ENV = ("HOME", "USERPROFILE", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "APPDATA", "LOCALAPPDATA")
PROTECTED_ENV = frozenset({
    *HOME_ENV,
    "PATH", "PATHEXT", "COMSPEC", "SYSTEMROOT", "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP",
    "LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH", "NODE_OPTIONS",
    "BASH_ENV", "ENV", "PERL5OPT", "RUBYOPT",
})


def _child_env(extra: Mapping[str, str], home: Path) -> dict:
    """Allowlisted worker variables without secrets, an empty home of its own, then ``extra``.

    CLI logins live in the worker's home (~/.codex, ~/.claude, ~/.gemini, %APPDATA%), so the
    child gets a fresh one and does not find them. Proxy URLs with ``user:pass@`` are dropped.
    """
    env = {}
    for name, value in os.environ.items():
        if name.upper() in INHERITED_ENV and guard.may_inherit(name, value):
            env[name] = value
    for name in HOME_ENV:
        env[name] = str(home)
    env.update(extra)
    return env


def _verdict_type():
    """L2's Verdict when composed, else the identical-shape local fallback."""
    try:
        from courier_core.verification import Verdict as L2Verdict
        return L2Verdict
    except ImportError:  # lane-local testing without the L2 controller tree
        @dataclass(frozen=True)
        class LocalVerdict:
            accepted: bool
            reason: str = ""
            retryable: bool = False
            verifier: Any = None
        return LocalVerdict


def _reject(reason: str, retryable: bool = False):
    return _verdict_type()(False, str(reason)[:500], bool(retryable), None)


def _accept(reason: str):
    return _verdict_type()(True, str(reason)[:500], False, None)


class LocalShellError(ValueError):
    """Bad local_shell params or sandbox; never a verification verdict."""


class LocalShellTimeout(RuntimeError):
    """The command outlived ``timeout_s`` and was killed (never-finishes analog)."""


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """Terminate child process and its process tree to prevent orphan processes."""
    pid = getattr(proc, "pid", None)
    if isinstance(pid, int) and pid > 0 and pid != os.getpid():
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
                shell=False,
            )
        else:
            try:
                os.killpg(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.communicate(timeout=5)
    except Exception:
        pass


def _reject_unspawnable_argv(command: Sequence[str]) -> None:
    """Reject argv values ``subprocess`` cannot spawn (embedded NUL, bad encoding, bypass flags)."""
    for arg in command:
        if "\0" in arg:
            raise LocalShellError("command argv must not contain embedded null bytes")
        if arg in FORBIDDEN_COMMAND_FLAGS or "--dangerously-skip-permissions" in arg:
            raise LocalShellError("command argv contains forbidden permission-bypass flag")
        try:
            os.fsencode(arg)
        except (UnicodeError, ValueError) as exc:
            raise LocalShellError(f"command argv cannot be encoded for spawn: {exc}") from exc


def _params(params: Mapping[str, Any]) -> dict:
    """Validate local_shell params; raise LocalShellError describing the first gap."""
    if not isinstance(params, Mapping):
        raise LocalShellError("local_shell params must be a mapping")
    command = params.get("command")
    if (not isinstance(command, Sequence) or isinstance(command, (str, bytes))
            or not command or any(not isinstance(a, str) or not a for a in command)):
        raise LocalShellError("command must be a non-empty argv list of non-empty strings")
    _reject_unspawnable_argv(command)
    provider = guard.provider_in_argv(command)
    if provider is not None:
        raise LocalShellError(f"command starts the provider CLI {provider!r}; use provider_exec, which gates its cost")
    out = {
        "command": list(command),
        "write": params.get("write", "out.txt"),
        "timeout_s": params.get("timeout_s", 60),
        "env": params.get("env", {}),
    }
    if not isinstance(out["write"], str) or not is_safe_name(out["write"]):
        raise LocalShellError("write must be a safe workspace-relative file name")
    if (isinstance(out["timeout_s"], bool) or not isinstance(out["timeout_s"], (int, float))
            or not (0 < out["timeout_s"] <= MAX_TIMEOUT_S)):
        raise LocalShellError(f"timeout_s must be a number in (0, {MAX_TIMEOUT_S}]")
    if not isinstance(out["env"], Mapping) or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in out["env"].items()):
        raise LocalShellError("env must be a mapping of str to str")
    for name, value in out["env"].items():
        if guard.is_credential_name(name) or guard.has_userinfo(value):
            raise LocalShellError(f"env must not carry a credential ({name}); task params are journaled")
        if guard.is_login_pointer(name):
            raise LocalShellError(f"env variable {name} is not allowed (login or provider configuration)")
        if name.upper() in PROTECTED_ENV:
            raise LocalShellError(f"env variable {name} is not allowed (path or loader override)")
    return out


@dataclass(frozen=True)
class RunResult:
    """Outcome of :func:`run`: what the host reports to the controller."""
    outcome: str  # "success" | "failure"
    artifacts: list = field(default_factory=list)  # [{path, sha256, size}]
    reason: str = ""
    retryable: bool = False


def run(params: Mapping[str, Any], workdir: str | os.PathLike, attempt: int = 1) -> RunResult:
    """Execute one bounded local_shell attempt with ``cwd=workdir``.

    The child is spawned with no shell and a hard ``timeout_s`` bound; expiry
    kills and reaps it, then raises :class:`LocalShellTimeout`. A non-zero
    exit becomes a non-retryable ``failure`` (the command ran; retrying the
    same bytes is a controller decision, not an adapter default). Exit zero
    with the declared evidence file present becomes ``success`` with its
    ``{path, sha256, size}``; exit zero without that file becomes a
    non-retryable ``failure`` (the command broke its evidence contract).
    ``attempt`` is accepted for host-interface symmetry and validated.
    """
    cfg = _params(params)
    root = Path(workdir)
    if not isinstance(attempt, int) or attempt < 1:
        raise LocalShellError("attempt must be an int >= 1")
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise LocalShellError(f"unusable workdir: {exc}") from exc
    # The empty home lives outside the workdir, so caches written there never become evidence.
    try:
        home = Path(tempfile.mkdtemp(prefix="courier-home-"))
    except OSError as exc:
        raise LocalShellError(f"no temporary home for the child: {exc}") from exc
    try:
        return _run_in(cfg, root, _child_env(cfg["env"], home))
    finally:
        _remove_tree(home)


def _remove_tree(path: Path) -> None:
    """Best-effort removal; Windows refuses to delete read-only files until the bit is cleared."""
    def clear_and_retry(func, target, _exc):
        try:
            os.chmod(target, 0o700)
            func(target)
        except OSError:
            pass
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=clear_and_retry)
    else:
        shutil.rmtree(path, onerror=clear_and_retry)


def _run_in(cfg: dict, root: Path, env: dict) -> RunResult:
    popen_kwargs: dict[str, Any] = {
        "cwd": str(root),
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "shell": False,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True

    try:
        proc = subprocess.Popen(cfg["command"], **popen_kwargs)
    except (OSError, ValueError) as exc:
        raise LocalShellError(f"local_shell command could not start: {exc}") from exc

    try:
        stdout_bytes, stderr_bytes = proc.communicate(timeout=cfg["timeout_s"])
    except subprocess.TimeoutExpired as exc:
        _kill_process_tree(proc)
        raise LocalShellTimeout(
            f"local_shell command outlived {cfg['timeout_s']}s and was killed") from exc
    except BaseException:
        _kill_process_tree(proc)
        raise

    if proc.returncode != 0:
        tail = stderr_bytes.decode("utf-8", errors="replace")[-500:]
        return RunResult("failure", [],
                         f"command exited {proc.returncode}: {tail}".strip() or
                         f"command exited {proc.returncode}", False)
    evidence = root / cfg["write"]
    try:
        data = evidence.read_bytes()
    except OSError:
        return RunResult("failure", [], "command produced no evidence file", False)
    digest = hashlib.sha256(data).hexdigest()
    return RunResult("success", [{"path": cfg["write"], "sha256": digest, "size": len(data)}])


def _payload_artifacts(payload: Mapping[str, Any]) -> list | None:
    artifacts = payload.get("artifacts", [])
    if not isinstance(artifacts, list) or not artifacts:
        return None
    return artifacts


def verify(task: Any, result: Any, home: str | os.PathLike):
    """Independently verify a RESULT_READY payload; pure and read-only.

    Returns accept only when every artifact reference resolves inside ``home``
    to bytes hashing to the claimed sha256, bound to this dispatch. Rejects
    everything else, including failures (with the controller's retryability
    default), evidence bound to another dispatch, empty or malformed evidence,
    and missing/tampered files. Attempt staleness and duplication stay the
    controller journal's job (fencing + dedupe keys): this function judges
    evidence only and changes no state.
    """
    try:
        return _verify(task, result, home)
    except Exception as exc:  # fail closed: a verifier never raises past here
        return _reject(f"verifier internal error: {type(exc).__name__}")


def _verify(task: Any, result: Any, home: str | os.PathLike):
    payload = result.payload
    if not isinstance(payload, Mapping):
        return _reject("malformed result payload")
    if payload.get("outcome") != "success":
        reason = payload.get("reason") or "worker reported failure"
        retryable = payload.get("retryable", getattr(task, "effect_class", "") == "idempotent")
        return _reject(reason, retryable)
    task_dispatch = getattr(task, "dispatch_id", None)
    result_dispatch = getattr(result, "dispatch_id", None)
    if task_dispatch is not None and result_dispatch != task_dispatch:
        return _reject("evidence is bound to a different dispatch")
    artifacts = _payload_artifacts(payload)
    if artifacts is None:
        return _reject("missing evidence" if isinstance(payload.get("artifacts"), list) else "malformed evidence")
    try:
        scope = Path(home).resolve()
    except OSError:
        return _reject("unreadable evidence scope")
    for ref in artifacts:
        if not isinstance(ref, Mapping):
            return _reject("malformed evidence")
        name, digest = ref.get("path"), ref.get("sha256")
        if not is_safe_name(name):
            return _reject("evidence artifact path escapes the work scope")
        if not isinstance(digest, str) or not SHA256_RE.match(digest):
            return _reject("evidence artifact sha256 is malformed")
        try:
            candidate = (scope / name).resolve()
        except OSError:
            return _reject("unreadable evidence file")
        if candidate != scope and scope not in candidate.parents:
            return _reject("evidence artifact path escapes the work scope")
        try:
            data = candidate.read_bytes()
        except OSError:
            return _reject("evidence file missing")
        if hashlib.sha256(data).hexdigest() != digest:
            return _reject("evidence artifact hash does not match")
    return _accept("local_shell evidence verified")


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - manual probe hook
    """Probe hook: python -m adapters.local_shell '<utf8 text>' <workdir>."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: python -m adapters.local_shell '<text>' <workdir>", file=sys.stderr)
        return 2
    res = run({"command": [sys.executable, "-c",
                           "import sys; open('out.txt', 'w').write(sys.argv[1])", args[0]],
               "write": "out.txt"}, args[1])
    print(res)
    return 0 if res.outcome == "success" else 1
