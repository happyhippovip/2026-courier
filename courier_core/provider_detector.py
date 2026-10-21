"""Fail-closed provider CLI surface and capability detection (S04).

Detects availability, executable paths, version strings, and supported flags
for allowlisted headless providers (e.g. agy, muse) without triggering paid
API calls, model inference, or network spend.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from courier_worker.adapters.provider_exec import (
    ALLOWED_PROVIDERS,
    resolve_binary,
)

_VERSION_RE = re.compile(r"(\d+\.\d+(?:\.\d+)?)")


@dataclass(frozen=True)
class ProviderCapabilityInfo:
    provider: str
    available: bool
    binary: str | None = None
    version: str | None = None
    capabilities: tuple[str, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_provider_cli(
    provider: str,
    config: Mapping[str, Any] | None = None,
    timeout_s: float = 5.0,
) -> ProviderCapabilityInfo:
    """Detect provider CLI surface and capabilities fail-closed without paid API calls."""
    if not isinstance(provider, str) or not provider.strip():
        return ProviderCapabilityInfo(
            provider="",
            available=False,
            reason="INVALID_PROVIDER_NAME",
        )
    prov = provider.strip().lower()
    if prov not in ALLOWED_PROVIDERS:
        return ProviderCapabilityInfo(
            provider=prov,
            available=False,
            reason="PROVIDER_NOT_ALLOWLISTED",
        )

    binary = resolve_binary(prov, config)
    if not binary:
        return ProviderCapabilityInfo(
            provider=prov,
            available=False,
            reason="BINARY_MISSING",
        )

    # Build bounded, zero-cost probe command (strictly NO inference, NO prompts)
    cmd: list[str]
    if os.name == "nt" and binary.lower().endswith(".py"):
        cmd = [sys.executable, binary, "--version"]
    else:
        cmd = [binary, "--version"]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=max(0.5, min(timeout_s, 15.0)),
            stdin=subprocess.DEVNULL,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ProviderCapabilityInfo(
            provider=prov,
            available=False,
            binary=binary,
            reason="PROBE_TIMEOUT",
        )
    except OSError as exc:
        return ProviderCapabilityInfo(
            provider=prov,
            available=False,
            binary=binary,
            reason=f"PROBE_EXEC_ERROR: {exc}",
        )

    out = (proc.stdout or b"").decode("utf-8", errors="replace") + " " + (proc.stderr or b"").decode("utf-8", errors="replace")

    # If --version returned non-zero (some tools only support --help), try --help safely
    if proc.returncode != 0:
        if os.name == "nt" and binary.lower().endswith(".py"):
            help_cmd = [sys.executable, binary, "--help"]
        else:
            help_cmd = [binary, "--help"]
        try:
            help_proc = subprocess.run(
                help_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=max(0.5, min(timeout_s, 15.0)),
                stdin=subprocess.DEVNULL,
                shell=False,
                check=False,
            )
            if help_proc.returncode == 0:
                out += " " + (help_proc.stdout or b"").decode("utf-8", errors="replace")
                proc = help_proc
        except Exception:
            pass

    if proc.returncode != 0:
        return ProviderCapabilityInfo(
            provider=prov,
            available=False,
            binary=binary,
            reason=f"PROBE_NONZERO_EXIT: {proc.returncode}",
        )

    match = _VERSION_RE.search(out)
    version = match.group(1) if match else "unknown"

    caps = []
    lower_out = out.lower()
    if prov == "agy":
        caps.append("headless")
        if "--sandbox" in lower_out or "sandbox" in lower_out:
            caps.append("sandbox")
        if "--output-format" in lower_out or "output-format" in lower_out or "json" in lower_out:
            caps.append("json_output")
        if "--print-timeout" in lower_out or "print-timeout" in lower_out:
            caps.append("print_timeout")
        if "plan" in lower_out:
            caps.append("plan_mode")
    elif prov == "muse":
        caps.append("headless")
        if "exec" in lower_out:
            caps.append("exec_subcommand")
        if "--prompt-file" in lower_out or "prompt-file" in lower_out:
            caps.append("prompt_file")
        if "--reasoning-effort" in lower_out or "reasoning-effort" in lower_out:
            caps.append("reasoning_effort")

    return ProviderCapabilityInfo(
        provider=prov,
        available=True,
        binary=binary,
        version=version,
        capabilities=tuple(caps),
        reason="CLI_DETECTED",
    )


def detect_all_providers(
    config: Mapping[str, Any] | None = None,
    timeout_s: float = 5.0,
) -> dict[str, ProviderCapabilityInfo]:
    """Scan all allowlisted providers and return capability mapping fail-closed."""
    results = {}
    for prov in sorted(ALLOWED_PROVIDERS):
        results[prov] = detect_provider_cli(prov, config=config, timeout_s=timeout_s)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Courier Provider CLI Capability Detector (S04)")
    parser.add_argument("--provider", choices=list(ALLOWED_PROVIDERS), help="Target provider to detect")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    args = parser.parse_args(argv)

    if args.provider:
        res = detect_provider_cli(args.provider)
        if args.json:
            print(json.dumps(res.to_dict(), indent=2))
        else:
            print(f"Provider: {res.provider} | Available: {res.available} | Version: {res.version} | Reason: {res.reason}")
        return 0 if res.available else 1
    else:
        results = detect_all_providers()
        if args.json:
            print(json.dumps({k: v.to_dict() for k, v in results.items()}, indent=2))
        else:
            for prov, res in results.items():
                print(f"Provider: {prov:8} | Available: {str(res.available):5} | Version: {str(res.version):10} | Reason: {res.reason}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
