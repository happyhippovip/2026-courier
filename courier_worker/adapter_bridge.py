"""Allowlisted adapter bridge (lane L3): declarative claim spec -> trusted runner.

The controller decides WHAT runs (``spec.adapter`` + ``spec.params``); the
worker decides HOW. A claim never carries a command line: the host maps an
allowlisted adapter name to Courier's own runner script and hands it the
params through a request file it writes itself. Nothing from the task can
name a module, a function, an executable or a shell fragment:

- ``ADAPTERS`` is a closed dict; an unknown name is a :class:`SpecError`.
- params are validated up front by the adapter's own validator, so malformed
  input is refused before ``/start`` and before any process exists.
- the runner argv is built only from ``sys.executable``, the absolute path
  of :mod:`courier_worker.adapter_runner` and a host-generated request path.

Layout under ``<home>`` (all host-owned):

- ``run/requests/<dispatch>.json``  what the runner must do (written by the host)
- ``run/reports/<dispatch>.json``   the adapter's structured outcome (written by the runner)
- ``artifacts/<dispatch>/``         the adapter's only writable directory

Artifacts are reported to the controller as paths relative to ``<home>``
(``artifacts/<dispatch>/<name>``), which is the scope the controller's
verifier reads from.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from courier_worker.host import SpecError

MAX_PARAMS_BYTES = 64 * 1024
EFFECT_KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,200}$")
REPORT_OUTCOMES = frozenset({"success", "failure"})


def _validate_synthetic(params: dict) -> dict:
    try:
        from adapters import synthetic  # trusted Courier adapter (lane L4)
    except ImportError as exc:
        raise SpecError(f"adapter implementation unavailable on this worker: {exc}") from None
    try:
        return synthetic._params(params)
    except synthetic.SyntheticError as exc:
        raise SpecError(f"synthetic params rejected: {exc}") from None


# adapter name -> params validator. Closed: adding an adapter is a code change.
ADAPTERS: Dict[str, Callable[[dict], dict]] = {
    "synthetic": _validate_synthetic,
}

RUNNER_SCRIPT = str(Path(__file__).resolve().with_name("adapter_runner.py"))


def _safe(dispatch_id: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in dispatch_id) or "unnamed"


def request_path(home: str, dispatch_id: str) -> str:
    return os.path.join(home, "run", "requests", f"{_safe(dispatch_id)}.json")


def report_path(home: str, dispatch_id: str) -> str:
    return os.path.join(home, "run", "reports", f"{_safe(dispatch_id)}.json")


def validate_request(spec: Any) -> tuple:
    """Return (adapter, params, effect_key) from a claim spec or raise SpecError."""
    if not isinstance(spec, dict):
        raise SpecError("claim carries no spec object")
    if "argv" in spec:
        raise SpecError("claim spec must not carry argv; the worker never runs a supplied command")
    adapter = spec.get("adapter")
    if not isinstance(adapter, str) or adapter not in ADAPTERS:
        raise SpecError(f"adapter {adapter!r} is not allowlisted on this worker")
    params = spec.get("params")
    if not isinstance(params, dict):
        raise SpecError("claim spec params must be an object")
    try:
        encoded = json.dumps(params, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
        raise SpecError("claim spec params are not plain JSON") from None
    if len(encoded.encode("utf-8")) > MAX_PARAMS_BYTES:
        raise SpecError("claim spec params exceed the size bound")
    ADAPTERS[adapter](params)
    effect_key = spec.get("effect_key")
    if effect_key is not None and (not isinstance(effect_key, str) or not EFFECT_KEY_RE.match(effect_key)):
        raise SpecError("claim spec effect_key is malformed")
    return adapter, params, effect_key


def runner_argv(home: str, dispatch_id: str) -> tuple:
    return (sys.executable, RUNNER_SCRIPT, request_path(home, dispatch_id))


def _atomic_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_request(home: str, spec: Any) -> str:
    """Persist what the runner must do; returns the request path."""
    path = request_path(home, spec.dispatch_id)
    try:
        os.unlink(report_path(home, spec.dispatch_id))  # never read a stale report
    except OSError:
        pass
    _atomic_json(path, {
        "adapter": spec.adapter, "params": spec.params, "attempt": spec.attempt,
        "task_id": spec.task_id, "dispatch_id": spec.dispatch_id, "effect_key": spec.effect_key,
        "workdir": spec.artifact_dir, "report": report_path(home, spec.dispatch_id),
    })
    return path


def read_report(home: str, dispatch_id: str) -> Optional[dict]:
    """The runner's structured outcome, or None if absent or malformed."""
    try:
        with open(report_path(home, dispatch_id), encoding="utf-8") as fh:
            report = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(report, dict) or report.get("outcome") not in REPORT_OUTCOMES:
        return None
    if not isinstance(report.get("retryable", False), bool):
        return None
    return report


def cleanup(home: str, dispatch_id: str) -> None:
    for path in (request_path(home, dispatch_id), report_path(home, dispatch_id)):
        try:
            os.unlink(path)
        except OSError:
            pass
