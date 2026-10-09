"""Headless provider exec adapter.

For an allowlisted provider, run one headless CLI from an absolute or configured
binary. ``muse`` writes the task prompt into a temp file in the task workdir and
runs ``<binary> exec --prompt-file <file>`` plus an allow-listed policy. ``agy``
runs ``<binary> -p <prompt> --output-format json --sandbox --disable-slash-commands
--print-timeout <N>s`` with stdin closed and cwd set to the task workdir. The
binary comes from host config or ``COURIER_PROVIDER_<NAME>_BIN``, never from
the task text. Policy values come only from explicit task fields. ``--yolo``,
``--disable-approval``, ``--disable-sandbox``, ``--sandbox-network``, and
``--dangerously-skip-permissions`` are never passed.

The worker allowlist (``courier_worker.adapter_bridge`` and
``courier_worker.adapter_runner``) is owned by another change. This module is
the implementation those files register; callers can import it directly.

One provider process runs at a time in this worker process. A second call
while one is active is deferred and does not launch. Before launch, the
resource governor is asked to admit a HEAVY job when that module imports.
Denial, or a governor that cannot be consulted, parks the run and does not
start the provider.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from adapters.synthetic import is_safe_name

ALLOWED_PROVIDERS = frozenset({"muse", "agy"})
FORBIDDEN_FLAGS = frozenset({"--yolo", "--disable-approval", "--disable-sandbox", "--sandbox-network"})
FORBIDDEN_KEYS = frozenset({
    "yolo", "disable_sandbox", "disable-sandbox", "disable_approval", "disable-approval",
})
APPROVAL_MODES = frozenset({"untrusted", "on-request", "never"})
DEFAULT_APPROVAL_MODE = "never"
DEFAULT_MAX_MODEL_STEPS = 15
MAX_MODEL_STEPS = 200
DEFAULT_MAX_TOOL_OUTPUT_BYTES = 65_536
MAX_TOOL_OUTPUT_BYTES = 1_048_576
# muse 1.4.3 names --reasoning-effort but the supplied help excerpt did not list
# the legal levels. Headless Courier will pass only this closed set.
REASONING_EFFORTS = frozenset({"low", "medium", "high"})
# muse 1.4.3 names --model, but no model id was in that evidence. None are accepted.
MODELS = frozenset()
# agy 1.3.1 / 1.2.14 defaults --print-timeout to 0 (wait forever). Always pass one.
AGY_DEFAULT_PRINT_TIMEOUT_S = 300
AGY_MAX_PRINT_TIMEOUT_S = 3600
AGY_EFFORTS = frozenset({"low", "medium", "high"})
AGY_MODES = frozenset({"plan", "accept-edits"})
AGY_SUCCESS_EVIDENCE = b'{"provider":"agy","status":"SUCCESS"}\n'
AGY_PARAM_KEYS = frozenset({
    "provider", "prompt", "timeout_s", "print_timeout_s",
    "model", "effort", "mode", "json_schema",
    "argv", "args", "flags", "extra_args", "command",
    "dangerously_skip_permissions", "dangerously-skip-permissions",
    "continue", "conversation", "remote_control", "remote-control",
    "prompt_interactive", "prompt-interactive", "add_dir", "add-dir",
    "new_project", "new-project", "project",
})
AGY_FORBIDDEN_NAMES = frozenset({
    "dangerously_skip_permissions", "continue", "conversation", "remote_control",
    "prompt_interactive", "add_dir", "new_project", "project",
})
AGY_FORBIDDEN_FLAGS = frozenset({
    "--dangerously-skip-permissions", "--continue", "-c", "--conversation",
    "--remote-control", "--prompt-interactive", "-i", "--add-dir",
    "--new-project", "--project", "--no-sandbox",
})
_AGY_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_AGY_APPROVAL_NOTE = re.compile(
    r"soft[-\s]?denied|approval[-\s]?refused|requires approval|permission denied",
    re.IGNORECASE,
)
KNOWN_PARAM_KEYS = frozenset({
    "provider", "prompt", "timeout_s",
    "approval_mode", "max_model_steps", "max_tool_output_bytes",
    "disable_web_tools", "no_foreign_personal_context",
    "reasoning_effort", "model",
    "argv", "args", "flags", "extra_args", "command",
})
DEFAULT_TIMEOUT_S = 1800.0
MAX_OUTPUT_BYTES = 64 * 1024
TRUNCATION_MARKER = b"\n[output truncated]\n"

_slot = threading.Lock()


class ProviderExecError(ValueError):
    """The task spec cannot be run. ``reason_code`` is safe to show."""

    def __init__(self, reason_code: str):
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True)
class ProviderResult:
    """One attempt. ``verified`` is true only for a success whose hash matches."""

    outcome: str
    reason_code: str | None = None
    exit_code: int | None = None
    output: bytes = b""
    output_sha256: str | None = None
    launched: bool = False
    parked: bool = False
    blocked: bool = False
    truncated: bool = False

    @property
    def verified(self) -> bool:
        if self.outcome != "success" or not isinstance(self.output_sha256, str):
            return False
        return hashlib.sha256(self.output).hexdigest() == self.output_sha256

    @property
    def retryable(self) -> bool:
        """Only a parked run may be tried later. This module does not retry."""
        return self.outcome == "deferred"

    @property
    def reason(self) -> str:
        """Safe report text: reason code, exit, and output hash. No paths."""
        parts = []
        if self.reason_code:
            parts.append(self.reason_code)
        if self.exit_code is not None:
            parts.append(f"exit={self.exit_code}")
        if self.output_sha256:
            parts.append(f"output_sha256={self.output_sha256}")
        return " ".join(parts)[:500]


def validate(params: Mapping) -> dict:
    """Normalize a task spec or raise ``ProviderExecError``."""
    if not isinstance(params, Mapping):
        raise ProviderExecError("BAD_PARAMS")
    if params.get("provider") == "agy":
        return _validate_agy(params)
    _reject_unknown_or_forbidden(params)
    provider = params.get("provider")
    if provider not in ALLOWED_PROVIDERS:
        raise ProviderExecError("PROVIDER_NOT_ALLOWLISTED")
    prompt = params.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ProviderExecError("BAD_PROMPT")
    for key in ("argv", "args", "flags", "extra_args", "command"):
        if key in params and params.get(key) not in (None, [], ""):
            raise ProviderExecError("ARGV_REJECTED")
    timeout = params.get("timeout_s", DEFAULT_TIMEOUT_S)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ProviderExecError("BAD_TIMEOUT")
    timeout_s = float(timeout)
    if not (0 < timeout_s <= DEFAULT_TIMEOUT_S):
        raise ProviderExecError("BAD_TIMEOUT")
    return {"provider": provider, "prompt": prompt, "timeout_s": timeout_s, **_scoped_fields(params)}


def admit_heavy() -> bool:
    """Ask the existing governor to admit one HEAVY job. Fail closed."""
    try:
        from scripts.resource_governor import governor
    except ImportError:
        return False
    try:
        return bool(governor.admit_job("HEAVY"))
    except Exception:
        return False


def run(params: Mapping, workdir, attempt: int = 1, *, config: Mapping | None = None) -> ProviderResult:
    """Run one provider attempt. Never retries and never invents a success."""
    try:
        spec = validate(params)
    except ProviderExecError as exc:
        return _finish("rejected", exc.reason_code)
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        return _finish("rejected", "BAD_ATTEMPT")
    if config is not None and not isinstance(config, Mapping):
        return _finish("UNAVAILABLE", "BAD_CONFIG", blocked=True)
    binary = resolve_binary(spec["provider"], config)
    if binary is None:
        return _finish("UNAVAILABLE", "BINARY_MISSING", blocked=True)
    if not _slot.acquire(blocking=False):
        return _finish("deferred", "PROVIDER_BUSY", parked=True)
    try:
        if not admit_heavy():
            return _finish("deferred", "ADMISSION_DENIED", parked=True)
        return _execute(spec, workdir, binary, _output_cap(config))
    finally:
        _slot.release()


def resolve_binary(provider: str, config: Mapping | None) -> str | None:
    """Host config, else ``COURIER_PROVIDER_<NAME>_BIN``. Missing means unusable."""
    chosen = _configured_binary(provider, config)
    if chosen is None:
        return None
    path = Path(chosen)
    if provider == "agy" and not path.is_absolute():
        return None
    try:
        is_file = path.is_file()
    except OSError:
        return None
    if not is_file:
        return None
    if os.name != "nt" and not os.access(path, os.X_OK):
        return None
    return str(path)


def build_argv(binary: str, prompt_file: str, policy: Mapping | None = None) -> list[str]:
    """Argv list. A Windows ``.py`` binary is started with this interpreter.

    Scoped flags follow ``--prompt-file`` so the prompt path stays a file
    argument. The prompt text itself is never copied onto argv.
    """
    if policy is None:
        policy = {}
    if not isinstance(policy, Mapping):
        raise ProviderExecError("BAD_PARAMS")
    _reject_unknown_or_forbidden(policy)
    tail = _flag_tail(_scoped_fields(policy))
    if os.name == "nt" and binary.lower().endswith(".py"):
        argv = [sys.executable, binary, "exec", "--prompt-file", prompt_file, *tail]
    else:
        argv = [binary, "exec", "--prompt-file", prompt_file, *tail]
    if any(_forbidden_token(arg) for arg in argv):
        raise ProviderExecError("FORBIDDEN_FLAG")
    return argv


def _configured_binary(provider: str, config: Mapping | None) -> str | None:
    config = config or {}
    binaries = config.get("binaries")
    if isinstance(binaries, Mapping) and provider in binaries:
        value = binaries.get(provider)
    else:
        value = os.environ.get(f"COURIER_PROVIDER_{provider.upper()}_BIN")
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def _output_cap(config: Mapping | None) -> int:
    raw = (config or {}).get("max_output_bytes", MAX_OUTPUT_BYTES)
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 1:
        return MAX_OUTPUT_BYTES
    return min(raw, MAX_OUTPUT_BYTES)


def _norm_key(key) -> str:
    return key.lower().replace("-", "_") if isinstance(key, str) else ""


def _forbidden_token(value) -> bool:
    return isinstance(value, str) and (value in FORBIDDEN_FLAGS or value.startswith("--sandbox-network"))


def _requests_forbidden(params: Mapping) -> bool:
    for key, value in params.items():
        if key == "prompt":
            continue
        norm = _norm_key(key)
        if norm == "sandbox_network" or (isinstance(key, str) and key.startswith("--sandbox-network")):
            return True
        if norm in {"yolo", "disable_sandbox", "disable_approval"} or key in FORBIDDEN_FLAGS:
            if value not in (False, None, [], ""):
                return True
        if _forbidden_token(value):
            return True
        if isinstance(value, list) and any(_forbidden_token(item) for item in value):
            return True
    return False


def _reject_unknown_or_forbidden(params: Mapping) -> None:
    if _requests_forbidden(params):
        raise ProviderExecError("FORBIDDEN_FLAG")
    if any(key not in KNOWN_PARAM_KEYS for key in params):
        raise ProviderExecError("UNKNOWN_KEY")


def _scoped_fields(params: Mapping) -> dict:
    if "approval_mode" not in params:
        approval = DEFAULT_APPROVAL_MODE
    else:
        approval = params["approval_mode"]
        if approval not in APPROVAL_MODES:
            raise ProviderExecError("BAD_APPROVAL_MODE")
    return {
        "approval_mode": approval,
        "max_model_steps": _bounded_int(
            params, "max_model_steps", DEFAULT_MAX_MODEL_STEPS, 1, MAX_MODEL_STEPS, "BAD_MODEL_STEPS",
        ),
        "max_tool_output_bytes": _bounded_int(
            params, "max_tool_output_bytes", DEFAULT_MAX_TOOL_OUTPUT_BYTES, 1,
            MAX_TOOL_OUTPUT_BYTES, "BAD_TOOL_OUTPUT",
        ),
        "disable_web_tools": _bool_flag(params, "disable_web_tools", True),
        "no_foreign_personal_context": _bool_flag(params, "no_foreign_personal_context", True),
        "reasoning_effort": _optional_member(params, "reasoning_effort", REASONING_EFFORTS, "REASONING_NOT_ALLOWLISTED"),
        "model": _optional_member(params, "model", MODELS, "MODEL_NOT_ALLOWLISTED"),
    }


def _bounded_int(params: Mapping, key: str, default: int, low: int, high: int, code: str) -> int:
    if key not in params:
        return default
    value = params[key]
    if isinstance(value, bool) or not isinstance(value, int) or value < low or value > high:
        raise ProviderExecError(code)
    return value


def _bool_flag(params: Mapping, key: str, default: bool) -> bool:
    if key not in params:
        return default
    value = params[key]
    if not isinstance(value, bool):
        raise ProviderExecError("BAD_BOOL")
    return value


def _optional_member(params: Mapping, key: str, allowed: frozenset, code: str):
    if key not in params or params[key] is None:
        return None
    value = params[key]
    if value not in allowed:
        raise ProviderExecError(code)
    return value


def _flag_tail(fields: Mapping) -> list[str]:
    tail = [
        "--approval-mode", fields["approval_mode"],
        "--max-model-steps", str(fields["max_model_steps"]),
        "--max-tool-output-bytes", str(fields["max_tool_output_bytes"]),
    ]
    if fields["disable_web_tools"]:
        tail.append("--disable-web-tools")
    if fields["no_foreign_personal_context"]:
        tail.append("--no-foreign-personal-context")
    if fields["reasoning_effort"]:
        tail.extend(["--reasoning-effort", fields["reasoning_effort"]])
    if fields["model"]:
        tail.extend(["--model", fields["model"]])
    return tail


def _validate_agy(params: Mapping) -> dict:
    _reject_agy(params)
    prompt = params.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip() or prompt.startswith("-"):
        raise ProviderExecError("BAD_PROMPT")
    for key in ("argv", "args", "flags", "extra_args", "command"):
        if key in params and params.get(key) not in (None, [], ""):
            raise ProviderExecError("ARGV_REJECTED")
    timeout_s, print_timeout_s = _agy_timeouts(params)
    spec = {
        "provider": "agy", "prompt": prompt, "timeout_s": timeout_s,
        "print_timeout_s": print_timeout_s,
    }
    model = _agy_model(params)
    if model:
        spec["model"] = model
    effort = _agy_choice(params, "effort", AGY_EFFORTS, "BAD_EFFORT")
    if effort:
        spec["effort"] = effort
    mode = _agy_choice(params, "mode", AGY_MODES, "BAD_MODE")
    if mode:
        spec["mode"] = mode
    if "json_schema" in params and params.get("json_schema") is not None:
        schema = params.get("json_schema")
        if not isinstance(schema, str) or not schema or schema.startswith("-") or not is_safe_name(schema):
            raise ProviderExecError("SCHEMA_ESCAPES")
        spec["json_schema"] = schema
    return spec


def _reject_agy(params: Mapping) -> None:
    if _requests_forbidden(params) or _agy_requests_forbidden(params):
        raise ProviderExecError("FORBIDDEN_FLAG")
    if any(key not in AGY_PARAM_KEYS for key in params):
        raise ProviderExecError("UNKNOWN_KEY")


def _agy_requests_forbidden(params: Mapping) -> bool:
    for key, value in params.items():
        if key == "prompt":
            continue
        norm = _norm_key(key)
        if norm in AGY_FORBIDDEN_NAMES or key in AGY_FORBIDDEN_FLAGS:
            if value not in (False, None, [], ""):
                return True
        if isinstance(value, str) and _agy_flag_token(value):
            return True
        if isinstance(value, list) and any(_agy_flag_token(item) for item in value):
            return True
    return False


def _agy_flag_token(value) -> bool:
    return isinstance(value, str) and (
        value in AGY_FORBIDDEN_FLAGS or value.startswith("--dangerously-skip-permissions")
    )


def _agy_timeouts(params: Mapping) -> tuple[float, int]:
    explicit = "timeout_s" in params
    timeout = params.get("timeout_s", DEFAULT_TIMEOUT_S)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ProviderExecError("BAD_TIMEOUT")
    timeout_s = float(timeout)
    if not (0 < timeout_s <= DEFAULT_TIMEOUT_S):
        raise ProviderExecError("BAD_TIMEOUT")
    if "print_timeout_s" in params:
        chosen = params.get("print_timeout_s")
        if (isinstance(chosen, bool) or not isinstance(chosen, int)
                or chosen < 1 or chosen > AGY_MAX_PRINT_TIMEOUT_S):
            raise ProviderExecError("BAD_PRINT_TIMEOUT")
    else:
        chosen = AGY_DEFAULT_PRINT_TIMEOUT_S
    if explicit:
        chosen = min(chosen, int(timeout_s))
        if chosen < 1:
            raise ProviderExecError("BAD_PRINT_TIMEOUT")
    return timeout_s, chosen


def _agy_model(params: Mapping) -> str | None:
    if "model" not in params or params.get("model") is None:
        return None
    value = params.get("model")
    if not isinstance(value, str) or not _AGY_SLUG.match(value):
        raise ProviderExecError("BAD_MODEL")
    return value


def _agy_choice(params: Mapping, key: str, allowed: frozenset, code: str) -> str | None:
    if key not in params or params.get(key) is None:
        return None
    value = params.get(key)
    if value not in allowed:
        raise ProviderExecError(code)
    return value


def build_agy_argv(binary: str, prompt: str, policy: Mapping | None = None, workdir=None) -> list[str]:
    """Argv for one sandboxed agy print. The prompt is one argument, not a shell string."""
    if not isinstance(binary, str) or not Path(binary).is_absolute():
        raise ProviderExecError("BINARY_NOT_ABSOLUTE")
    if not isinstance(prompt, str) or not prompt.strip() or prompt.startswith("-"):
        raise ProviderExecError("BAD_PROMPT")
    if policy is None:
        policy = {}
    if not isinstance(policy, Mapping):
        raise ProviderExecError("BAD_PARAMS")
    if policy.get("provider") == "agy" and "print_timeout_s" in policy:
        spec = policy
    else:
        merged = dict(policy)
        merged["provider"] = "agy"
        merged["prompt"] = prompt
        spec = _validate_agy(merged)
    argv = [
        binary, "-p", prompt, "--output-format", "json", "--sandbox",
        "--disable-slash-commands", "--print-timeout", f"{spec['print_timeout_s']}s",
    ]
    if spec.get("model"):
        argv.extend(["--model", spec["model"]])
    if spec.get("effort"):
        argv.extend(["--effort", spec["effort"]])
    if spec.get("mode"):
        argv.extend(["--mode", spec["mode"]])
    if spec.get("json_schema"):
        argv.extend(["--json-schema", _schema_rel(workdir, spec["json_schema"])])
    if any(_agy_flag_token(arg) for arg in argv):
        raise ProviderExecError("FORBIDDEN_FLAG")
    if os.name == "nt" and binary.lower().endswith(".py"):
        return [sys.executable, *argv]
    return argv


def _schema_rel(workdir, value: str) -> str:
    if workdir is None:
        raise ProviderExecError("SCHEMA_MISSING")
    root = Path(workdir).resolve()
    try:
        candidate = (root / value).resolve()
    except OSError:
        raise ProviderExecError("SCHEMA_ESCAPES") from None
    if candidate != root and root not in candidate.parents:
        raise ProviderExecError("SCHEMA_ESCAPES")
    try:
        is_file = candidate.is_file()
    except OSError:
        raise ProviderExecError("SCHEMA_MISSING") from None
    if not is_file:
        raise ProviderExecError("SCHEMA_MISSING")
    return Path(value).as_posix()


def _execute_agy(spec: dict, workdir, binary: str, cap: int) -> ProviderResult:
    try:
        root = Path(workdir).resolve()
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        return _finish("UNAVAILABLE", "WORKDIR_UNAVAILABLE", blocked=True)
    try:
        argv = build_agy_argv(binary, spec["prompt"], spec, root)
    except ProviderExecError as exc:
        return _finish("rejected", exc.reason_code)
    try:
        proc = _popen_agy(argv, str(root))
    except OSError:
        return _finish("UNAVAILABLE", "BINARY_MISSING", blocked=True)
    stdout, stderr, truncated, status, code = _wait_pair(proc, float(spec["print_timeout_s"]), cap)
    if status == "timeout":
        return _agy_result("ERROR", "TIMEOUT", b"", exit_code=None, truncated=True)
    return _interpret_agy(stdout, stderr, code, truncated)


def _interpret_agy(stdout: bytes, stderr: bytes, code: int | None, truncated: bool) -> ProviderResult:
    note = stderr.decode("utf-8", errors="replace")
    if _AGY_APPROVAL_NOTE.search(note):
        return _agy_result("BLOCKED", "PROVIDER_APPROVAL_REFUSED", b"", exit_code=code, blocked=True,
                           truncated=truncated)
    if truncated:
        return _agy_result("ERROR", "OUTPUT_TOO_LARGE", b"", exit_code=code, truncated=True)
    if code != 0:
        return _agy_result("ERROR", "NONZERO_EXIT", b"", exit_code=code)
    try:
        payload = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return _agy_result("ERROR", "INVALID_JSON", b"", exit_code=code)
    if not isinstance(payload, dict) or payload.get("status") != "SUCCESS":
        return _agy_result("ERROR", "PROVIDER_STATUS", b"", exit_code=code)
    return _agy_result("success", None, AGY_SUCCESS_EVIDENCE, exit_code=0)


def _agy_result(outcome: str, reason_code: str | None, output: bytes, *, exit_code: int | None,
                blocked: bool = False, truncated: bool = False) -> ProviderResult:
    return ProviderResult(
        outcome=outcome,
        reason_code=reason_code,
        exit_code=exit_code,
        output=output,
        output_sha256=hashlib.sha256(output).hexdigest(),
        launched=True,
        blocked=blocked,
        truncated=truncated,
    )


def _popen_agy(argv: list[str], cwd: str) -> subprocess.Popen:
    kwargs = {
        "args": argv,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "stdin": subprocess.DEVNULL,
        "cwd": cwd,
        "shell": False,
        "close_fds": True,
    }
    return subprocess.Popen(**kwargs)


def _pump(stream, cap: int):
    state = {"buf": bytearray(), "truncated": False}
    lock = threading.Lock()

    def _read() -> None:
        try:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                with lock:
                    if len(state["buf"]) >= cap:
                        state["truncated"] = True
                        continue
                    room = cap - len(state["buf"])
                    if len(chunk) > room:
                        state["buf"].extend(chunk[:room])
                        state["truncated"] = True
                    else:
                        state["buf"].extend(chunk)
        except (OSError, ValueError):
            return
        finally:
            try:
                stream.close()
            except OSError:
                pass

    thread = threading.Thread(target=_read, name="provider-exec-output", daemon=True)
    thread.start()
    return thread, state, lock


def _wait_pair(proc: subprocess.Popen, timeout_s: float, cap: int):
    out_thread, out_state, out_lock = _pump(proc.stdout, cap)
    err_thread, err_state, err_lock = _pump(proc.stderr, cap)
    status = "ok"
    code = None
    try:
        code = proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        status = "timeout"
        _kill_tree(proc)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    finally:
        if proc.poll() is None:
            _kill_tree(proc)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        out_thread.join(timeout=5)
        err_thread.join(timeout=5)
    with out_lock:
        stdout = bytes(out_state["buf"])
        out_truncated = out_state["truncated"]
    with err_lock:
        stderr = bytes(err_state["buf"])
        err_truncated = err_state["truncated"]
    return stdout, stderr, out_truncated or err_truncated, status, code


def _finish(outcome: str, reason_code: str, *, parked: bool = False, blocked: bool = False) -> ProviderResult:
    return ProviderResult(
        outcome=outcome, reason_code=reason_code, launched=False, parked=parked, blocked=blocked,
    )


def _hashed(outcome: str, reason_code: str | None, output: bytes, *, exit_code: int | None,
            truncated: bool) -> ProviderResult:
    return ProviderResult(
        outcome=outcome,
        reason_code=reason_code,
        exit_code=exit_code,
        output=output,
        output_sha256=hashlib.sha256(output).hexdigest(),
        launched=True,
        truncated=truncated,
    )


def _execute(spec: dict, workdir, binary: str, cap: int) -> ProviderResult:
    if spec.get("provider") == "agy":
        return _execute_agy(spec, workdir, binary, cap)
    try:
        prompt_file = _write_prompt(workdir, spec["prompt"])
    except OSError:
        return _finish("UNAVAILABLE", "WORKDIR_UNAVAILABLE", blocked=True)
    try:
        argv = build_argv(binary, prompt_file, spec)
    except ProviderExecError as exc:
        return _finish("rejected", exc.reason_code)
    try:
        proc = _popen(argv, cwd=str(workdir))
    except OSError:
        return _finish("UNAVAILABLE", "BINARY_MISSING", blocked=True)
    output, truncated, status, code = _wait(proc, spec["timeout_s"], cap)
    if status == "timeout":
        return _hashed("FAILED", "TIMEOUT", output, exit_code=None, truncated=truncated)
    if code == 0:
        return _hashed("success", None, output, exit_code=0, truncated=truncated)
    return _hashed("FAILED", "NONZERO_EXIT", output, exit_code=code, truncated=truncated)


def _write_prompt(workdir, prompt: str) -> str:
    root = Path(workdir)
    root.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="prompt-", suffix=".txt", dir=str(root))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(prompt)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise
    return name


def _popen(argv: list[str], cwd: str | None = None) -> subprocess.Popen:
    kwargs = {
        "args": argv,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
        "cwd": cwd,
        "shell": False,
        "close_fds": True,
    }
    return subprocess.Popen(**kwargs)


def _kill_tree(proc: subprocess.Popen) -> None:
    """Terminate this child and its own descendants. Do not signal anyone else."""
    pid = proc.pid
    if pid is None or pid <= 0 or pid == os.getpid():
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
            shell=False,
        )
        return
    try:
        proc.kill()
    except OSError:
        pass


def _wait(proc: subprocess.Popen, timeout_s: float, cap: int):
    state = {"buf": bytearray(), "truncated": False}
    lock = threading.Lock()

    def _read() -> None:
        stream = proc.stdout
        try:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    break
                with lock:
                    if len(state["buf"]) >= cap:
                        state["truncated"] = True
                        continue
                    room = cap - len(state["buf"])
                    if len(chunk) > room:
                        state["buf"].extend(chunk[:room])
                        state["truncated"] = True
                    else:
                        state["buf"].extend(chunk)
        except (OSError, ValueError):
            return
        finally:
            try:
                stream.close()
            except OSError:
                pass

    thread = threading.Thread(target=_read, name="provider-exec-output", daemon=True)
    thread.start()
    status = "ok"
    code = None
    try:
        code = proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        status = "timeout"
        _kill_tree(proc)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    finally:
        if proc.poll() is None:
            _kill_tree(proc)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        thread.join(timeout=5)
    with lock:
        output = bytes(state["buf"])
        truncated = state["truncated"]
    if truncated:
        output += TRUNCATION_MARKER
    return output, truncated, status, code
