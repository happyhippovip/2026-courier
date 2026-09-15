# SIMULATION / NON-PRODUCTION EVIDENCE
# THIS SCRIPT DEVIATES FROM COURIER V1 ARCHITECTURE AND WAS CREATED AS A SYNTHETIC OVERNIGHT TEST
#!/usr/bin/env python3
"""Windows link health check with bounded recovery and fail-closed semantics.

Wraps ~/Desktop/check-windows-ai-link.sh into a Python-callable gate:
  - Runs the health check with bounded retry (max 2 full attempts)
  - Parses structured key=value output
  - On transient TCP/SSH failure: waits and retries once
  - On persistent failure: returns failure with checkpoint data
  - Never loses or duplicates tasks
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
HEALTH_SCRIPT = Path.home() / "Desktop" / "check-windows-ai-link.sh"
CHECKPOINT_DIR = COURIER_DIR / "events" / "checkpoints"


def _parse_health_output(stdout: str) -> dict[str, str]:
    """Parses key=value lines from the health check script."""
    result = {}
    for line in stdout.strip().splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def _run_health_check(timeout: int = 30) -> tuple[bool, dict[str, str]]:
    """Runs the health check script once.  Returns (healthy, parsed_output)."""
    if not HEALTH_SCRIPT.exists():
        return False, {"RESULT": "SCRIPT_MISSING", "FAILURE_LAYER": "LOCAL_SCRIPT"}

    try:
        proc = subprocess.run(
            ["/bin/zsh", str(HEALTH_SCRIPT)],
            capture_output=True, text=True, timeout=timeout,
        )
        parsed = _parse_health_output(proc.stdout)
        healthy = proc.returncode == 0 and parsed.get("RESULT") == "READY"
        return healthy, parsed
    except subprocess.TimeoutExpired:
        return False, {"RESULT": "TIMEOUT", "FAILURE_LAYER": "LOCAL_TIMEOUT"}
    except Exception as e:
        return False, {"RESULT": "ERROR", "FAILURE_LAYER": f"EXCEPTION:{e}"}


# Layers that are safe for automatic bounded retry (transient network issues)
_RECOVERABLE_LAYERS = {"TCP22_UNREACHABLE", "SSH_AUTH_FAILURE", "LOCAL_TIMEOUT"}


def check_windows_health(
    max_attempts: int = 2,
    retry_delay_sec: int = 5,
) -> tuple[bool, dict[str, Any]]:
    """Full health check with bounded recovery.

    Returns:
        (healthy, health_report)
        health_report always contains: RESULT, FAILURE_LAYER, attempts, timestamp
    """
    all_attempts = []
    for attempt in range(1, max_attempts + 1):
        healthy, parsed = _run_health_check()
        attempt_record = {
            "attempt": attempt,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "healthy": healthy,
            **parsed,
        }
        all_attempts.append(attempt_record)

        if healthy:
            return True, {
                "RESULT": "READY",
                "FAILURE_LAYER": "NONE",
                "attempts": all_attempts,
                "timestamp": attempt_record["timestamp"],
                "NETWORK_ROUTE": parsed.get("NETWORK_ROUTE", ""),
                "TCP22": parsed.get("TCP22", ""),
                "SSH": parsed.get("SSH", ""),
                "REMOTE_HOSTNAME": parsed.get("REMOTE_HOSTNAME", ""),
                "REMOTE_PROJECT": parsed.get("REMOTE_PROJECT", ""),
            }

        failure_layer = parsed.get("FAILURE_LAYER", "UNKNOWN")
        if failure_layer not in _RECOVERABLE_LAYERS:
            # Non-recoverable failure → fail closed immediately
            break

        if attempt < max_attempts:
            print(f"[HEALTH_RECOVERY] Attempt {attempt} failed ({failure_layer}), retrying in {retry_delay_sec}s...")
            time.sleep(retry_delay_sec)

    last = all_attempts[-1]
    return False, {
        "RESULT": last.get("RESULT", "UNAVAILABLE"),
        "FAILURE_LAYER": last.get("FAILURE_LAYER", "UNKNOWN"),
        "attempts": all_attempts,
        "timestamp": last.get("timestamp", ""),
        "RECOMMENDED_ACTION": last.get("RECOMMENDED_ACTION", "MANUAL_INVESTIGATION"),
    }


def checkpoint_task(task_id: str, envelope: dict, health_report: dict) -> Path:
    """Saves a blocked task to the checkpoint directory for later retry.
    The task is NOT lost and NOT duplicated — it can be resumed."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "task_id": task_id,
        "checkpoint_reason": "WINDOWS_HEALTH_CHECK_FAILED",
        "failure_layer": health_report.get("FAILURE_LAYER", "UNKNOWN"),
        "checkpointed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "health_report": health_report,
        "envelope": envelope,
        "status": "CHECKPOINTED_BLOCKED",
    }
    path = CHECKPOINT_DIR / f"{task_id}-checkpoint.json"
    tmp = path.with_suffix(f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(checkpoint, indent=2) + "
", encoding="utf-8")
    os.replace(tmp, path)
    print(f"[CHECKPOINT] Task {task_id} checkpointed to {path.name}")
    return path


if __name__ == "__main__":
    healthy, report = check_windows_health()
    print(json.dumps(report, indent=2))
    if healthy:
        print("
WINDOWS_LINK=READY")
    else:
        print(f"
WINDOWS_LINK=BLOCKED (layer: {report.get('FAILURE_LAYER')})")
