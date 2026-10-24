"""Trusted adapter runner (lane L3): the only program the worker host spawns.

    python <this file> <request.json>

Run as a contained child of the worker host. It reads the host-written
request, re-checks the adapter against the allowlist, runs the adapter inside
its workdir and writes a structured report. Exit codes:

- 0  a report was written (success or an adapter-reported failure)
- 2  the request or the adapter is not acceptable (fail closed, no report)
- 3  the adapter crashed (synthetic ``crash_after_s``)
- 1  any other unexpected error

A synthetic ``hang`` really hangs: the process sleeps until the host's
timeout, lease or cancellation machinery terminates the owned tree.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

# The runner is started by path, not by module name, so the package root is
# derived from this file instead of trusting the inherited environment.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ALLOWED = frozenset({"synthetic", "local_shell", "provider_exec"})


def _write_report(path: str, report: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(report, fh, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _write_provider_evidence(workdir: str, output: bytes) -> None:
    """Save captured Muse output as provider_output.txt inside the task workdir.

    The controller verifier (adapters/provider_exec.py) accepts provider_exec
    only when this regular file is inside the Courier home and at most 1 MiB.
    Writing it is not a success signal. A symlink at the destination is
    removed rather than followed.
    """
    data = bytes(output[: 1024 * 1024]) if isinstance(output, (bytes, bytearray)) else b""
    fd, tmp = tempfile.mkstemp(dir=workdir, prefix=".tmp-provider-", suffix=".txt")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        dest = os.path.join(workdir, "provider_output.txt")
        if os.path.islink(dest):
            os.unlink(dest)
        os.replace(tmp, dest)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class _InputRefused(Exception):
    """The request's input cannot be trusted as the dependency's verified result."""


def _verified_input_files(bound, home) -> list:
    """Absolute paths of the input artifacts, each checked against its sha256.

    ``bound`` is the claim spec's input as the host wrote it into the request:
    artifact paths relative to ``home`` with the sha256 the controller journaled
    for the dependency's accepted result. A path outside home, a missing file
    or a hash mismatch refuses the whole input.
    """
    if not isinstance(bound, dict) or not isinstance(home, str) or not os.path.isabs(home):
        raise _InputRefused("malformed input")
    artifacts = bound.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise _InputRefused("input names no artifact")
    scope = Path(home).resolve()
    files = []
    for ref in artifacts:
        name = ref.get("path") if isinstance(ref, dict) else None
        digest = ref.get("sha256") if isinstance(ref, dict) else None
        if (not isinstance(name, str) or not name or "\\" in name or ":" in name or name.startswith("/")
                or any(part in ("", ".", "..") for part in name.split("/")) or not isinstance(digest, str)):
            raise _InputRefused("malformed input artifact")
        candidate = (scope / name).resolve()
        if scope not in candidate.parents:
            raise _InputRefused("input artifact path escapes the home")
        try:
            data = candidate.read_bytes()
        except OSError:
            raise _InputRefused("input artifact is missing") from None
        if hashlib.sha256(data).hexdigest() != digest:
            raise _InputRefused("input artifact hash does not match the verified result")
        files.append(str(candidate))
    return files


def main(argv: list) -> int:
    if len(argv) != 1:
        print("adapter_runner: expected exactly one request path", file=sys.stderr)
        return 2
    try:
        with open(argv[0], encoding="utf-8") as fh:
            request = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"adapter_runner: unreadable request: {exc}", file=sys.stderr)
        return 2
    adapter = request.get("adapter") if isinstance(request, dict) else None
    if adapter not in ALLOWED:
        print(f"adapter_runner: adapter {adapter!r} is not allowlisted", file=sys.stderr)
        return 2
    workdir, report = request.get("workdir"), request.get("report")
    attempt, params = request.get("attempt"), request.get("params")
    if not (isinstance(workdir, str) and isinstance(report, str) and isinstance(params, dict)
            and isinstance(attempt, int) and not isinstance(attempt, bool)):
        print("adapter_runner: malformed request", file=sys.stderr)
        return 2
    os.makedirs(workdir, exist_ok=True)

    input_files = None
    if "input" in request:
        try:
            input_files = _verified_input_files(request.get("input"), request.get("home"))
        except _InputRefused as exc:
            # The adapter never sees an input whose bytes are not the verified ones.
            print(f"adapter_runner: input refused: {exc}", file=sys.stderr)
            _write_report(report, {"outcome": "failure", "reason": f"input refused: {exc}"[:500], "retryable": False})
            return 0

    if adapter == "synthetic":
        from adapters import synthetic

        try:
            if input_files is None:
                result = synthetic.run(params, workdir, attempt)
            else:
                result = synthetic.run(params, workdir, attempt, input_files=input_files)
        except synthetic.SyntheticHang:
            print("adapter_runner: synthetic hang (waiting to be terminated)", file=sys.stderr, flush=True)
            while True:
                time.sleep(3600)
        except synthetic.SyntheticCrash as exc:
            print(f"adapter_runner: {exc}", file=sys.stderr)
            return 3
        except synthetic.SyntheticError as exc:
            print(f"adapter_runner: params rejected: {exc}", file=sys.stderr)
            return 2
    elif adapter == "local_shell":
        from adapters import local_shell
        from courier_core.controller import cost_admission
        from courier_core.verification import adapter_cost_class

        try:
            local_shell._params(params)
            # The controller checked the cost when the task was created; check again before
            # the command starts, so a task journaled before that gate existed cannot run.
            # (provider_exec has its own gate before its process starts.)
            blocked = cost_admission(adapter_cost_class("local_shell"), params)
            if blocked is not None:
                _write_report(report, {"outcome": "failure", "reason": f"cost_blocked: {blocked}"[:500],
                                       "retryable": False})
                print(f"adapter_runner: cost blocked: {blocked}", file=sys.stderr)
                return 0
            result = local_shell.run(params, workdir, attempt)
        except local_shell.LocalShellTimeout as exc:
            _write_report(report, {"outcome": "failure", "reason": str(exc)[:500], "retryable": True})
            return 0
        except local_shell.LocalShellError as exc:
            _write_report(report, {"outcome": "failure", "reason": str(exc)[:500], "retryable": False})
            print(f"adapter_runner: params rejected: {exc}", file=sys.stderr)
            return 2
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            _write_report(report, {
                "outcome": "failure",
                "reason": f"local_shell unexpected error: {type(exc).__name__}: {exc}"[:500],
                "retryable": False,
            })
            print(f"adapter_runner: local_shell crashed: {exc}", file=sys.stderr)
            return 1
    elif adapter == "provider_exec":
        from courier_worker.adapters import provider_exec
        result = provider_exec.run(params, workdir, attempt)
        _write_provider_evidence(workdir, result.output)
        _write_report(report, {
            "outcome": "success" if result.outcome == "success" else "failure",
            "reason": result.reason[:500],
            "retryable": bool(result.retryable),
        })
        return 0
    else:
        print(f"adapter_runner: adapter {adapter!r} is not allowlisted", file=sys.stderr)
        return 2
    _write_report(report, {"outcome": result.outcome, "reason": str(result.reason)[:500],
                           "retryable": bool(result.retryable)})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - never a silent or fake success
        print(f"adapter_runner: unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
