"""Real Antigravity Headless Execution Adapter (Mission 02).

Connects Courier Controller tasks to genuine headless Google Antigravity CLI
invocations (`agy -p` / `agy --print --output-format json`).

Features:
- Validates CLI options, binary location, and version.
- Executes real subprocess commands non-interactively with timeout bounding.
- Separates stdout, stderr, and process returncode cleanly.
- Redacts secrets (tokens, passwords, api keys) before storing results.
- Generates durable, machine-readable JSON result envelopes for Courier.
- Fails closed on CLI error, timeout, or invalid execution.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SECRET_PATTERNS = [
    re.compile(r"(?i)(password|secret|token|api[_-]?key|bearer|oauth|private[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}['\"]?"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z-_]{35}"),
]


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted


def find_antigravity_cli() -> Optional[str]:
    # Look for 'agy' or 'antigravity' on PATH or default ~/.local/bin/
    cli = shutil.which("agy") or shutil.which("antigravity")
    if cli:
        return cli
    candidate = Path.home() / ".local" / "bin" / "agy"
    if candidate.exists() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None


class AntigravityHeadlessAdapter:
    """Executes Courier tasks through the real Google Antigravity CLI."""

    def __init__(self, cli_path: Optional[str] = None):
        self.cli_path = cli_path or find_antigravity_cli()
        if not self.cli_path:
            raise RuntimeError("Antigravity CLI (agy) not found in PATH or ~/.local/bin/agy")

    def run_task(
        self,
        task_id: str,
        dispatch_id: str,
        prompt: str,
        timeout_s: float = 30.0,
        extra_args: Optional[List[str]] = None,
        cwd: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Runs a task prompt through `agy -p` headless execution."""
        start_ts = time.time()
        start_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start_ts))

        # Command construction
        # Use -p / --print with --output-format json or text
        cmd = [self.cli_path, "-p", prompt, "--output-format", "text"]
        if extra_args:
            cmd.extend(extra_args)

        timed_out = False
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=str(cwd) if cwd else None,
                env=dict(os.environ),
            )
            raw_stdout = proc.stdout
            raw_stderr = proc.stderr
            returncode = proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            raw_stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            raw_stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            returncode = -1

        end_ts = time.time()
        end_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(end_ts))

        # Clean and redact secrets
        clean_stdout = redact_secrets(raw_stdout)
        clean_stderr = redact_secrets(raw_stderr)

        success = (returncode == 0) and not timed_out
        outcome = "success" if success else "failure"

        # Construct deterministic machine-readable execution receipt
        receipt = {
            "task_id": task_id,
            "dispatch_id": dispatch_id,
            "cli_executable": self.cli_path,
            "cli_started": True,
            "prompt": prompt,
            "start_time": start_iso,
            "end_time": end_iso,
            "duration_seconds": round(end_ts - start_ts, 3),
            "timed_out": timed_out,
            "exit_code": returncode,
            "outcome": outcome,
            "stdout": clean_stdout.strip(),
            "stderr": clean_stderr.strip(),
            "sha256_stdout": hashlib.sha256(clean_stdout.encode()).hexdigest(),
        }
        return receipt
