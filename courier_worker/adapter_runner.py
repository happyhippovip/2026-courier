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

import json
import os
import sys
import tempfile
import time
from pathlib import Path

# The runner is started by path, not by module name, so the package root is
# derived from this file instead of trusting the inherited environment.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ALLOWED = frozenset({"synthetic"})


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

    from adapters import synthetic

    try:
        result = synthetic.run(params, workdir, attempt)
    except synthetic.SyntheticHang:
        print("adapter_runner: synthetic hang (waiting to be terminated)", file=sys.stderr, flush=True)
        while True:
            time.sleep(3600)
    except synthetic.SyntheticCrash as exc:
        print(f"adapter_runner: {exc}", file=sys.stderr)
        return 3
    except synthetic.SyntheticError as exc:
        _write_report(report, {"outcome": "failure", "reason": str(exc)[:500], "retryable": False})
        print(f"adapter_runner: params rejected: {exc}", file=sys.stderr)
        return 2
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        _write_report(report, {
            "outcome": "failure",
            "reason": f"synthetic unexpected error: {type(exc).__name__}: {exc}"[:500],
            "retryable": False,
        })
        print(f"adapter_runner: synthetic crashed: {exc}", file=sys.stderr)
        return 1
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
