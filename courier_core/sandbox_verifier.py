"""Security Policy Enforcement and Sandbox Jail Verifier (P37)

Provides fail-closed static and runtime sandbox verification, blocking
filesystem jail escapes, banned CLI utilities (grep/rg), destructive shell
commands, sensitive credential exfiltration, and unauthorized network egress.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    CAUTION = "CAUTION"
    CRITICAL_BLOCKED = "CRITICAL_BLOCKED"


@dataclass
class SandboxVerdict:
    allowed: bool
    risk_level: RiskLevel
    violations: List[str] = field(default_factory=list)
    version: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "risk_level": self.risk_level.value,
            "violations": list(self.violations),
            "version": self.version,
        }


BANNED_TOOLS: Set[str] = {
    "grep",
    "rg",
    "ripgrep",
    "select-string",
}

DESTRUCTIVE_PATTERNS: List[re.Pattern] = [
    re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\s+/", re.IGNORECASE),
    re.compile(r"\brmdir\s+/[sS]", re.IGNORECASE),
    re.compile(r"\bdel\s+.*(?:/[fFsS]|-[fFsS])\s+.*(?:windows|system32|c:\\)", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-zA-Z]:", re.IGNORECASE),
    re.compile(r":\(\)\s*{\s*:\|:&\s*};\s*:", re.IGNORECASE),  # fork bomb
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    re.compile(r"\bshred\b", re.IGNORECASE),
    re.compile(r"\bdd\s+if=", re.IGNORECASE),
    re.compile(r"\bgit\s+clean\s+-[a-zA-Z]*f[a-zA-Z]*", re.IGNORECASE),
    re.compile(r"\bgit\s+reset\s+--hard", re.IGNORECASE),
    re.compile(r"\bchmod\s+-[a-zA-Z]*R\s+777", re.IGNORECASE),
    re.compile(r"\breg\s+delete\b", re.IGNORECASE),
    re.compile(r"\bvssadmin\s+delete\b", re.IGNORECASE),
    re.compile(r"\bcipher\s+/[wW]", re.IGNORECASE),
]

SUSPICIOUS_EXEC_TOOLS: Set[str] = {
    "certutil",
    "bitsadmin",
    "mshta",
    "rundll32",
    "wscript",
    "cscript",
}

NETWORK_TOOLS: Set[str] = {
    "curl",
    "wget",
    "nc",
    "netcat",
    "ncat",
    "ssh",
    "scp",
    "ftp",
    "telnet",
}

SENSITIVE_FILENAME_PATTERNS: Set[str] = {
    ".env",
    "id_rsa",
    "id_ed25519",
    "wallet.json",
    "wallet.dat",
    "credentials.pfx",
    "seed.txt",
    "secrets.yaml",
}


class SandboxJailVerifier:
    """Enforces fail-closed security policies on commands and file operations."""

    def __init__(
        self,
        allowed_roots: Optional[List[Path | str]] = None,
        default_allow_network: bool = True,
    ) -> None:
        self.allowed_roots: List[Path] = [
            Path(r).resolve() for r in (allowed_roots or [Path.cwd()])
        ]
        self.default_allow_network = default_allow_network

    def verify_command(
        self,
        command: str | List[str],
        allow_network: Optional[bool] = None,
    ) -> SandboxVerdict:
        if isinstance(command, list):
            cmd_str = " ".join(command)
        else:
            cmd_str = str(command)

        violations: List[str] = []
        is_critical = False

        # 0. NUL-byte injection defense (V2)
        if "\x00" in cmd_str or (isinstance(command, list) and any("\x00" in str(arg) for arg in command)):
            return SandboxVerdict(
                allowed=False,
                risk_level=RiskLevel.CRITICAL_BLOCKED,
                violations=["Null byte injection detected in command arguments"],
                version="2.0",
            )

        # 1. Destructive shell command pattern check
        for pattern in DESTRUCTIVE_PATTERNS:
            if pattern.search(cmd_str):
                violations.append(f"Destructive system command pattern detected: '{pattern.pattern}'")
                is_critical = True

        # 2. Token extraction (including sub-tokens separated by shell operators ;, |, &)
        try:
            raw_tokens = shlex.split(cmd_str, posix=os.name != "nt")
        except Exception:
            raw_tokens = cmd_str.split()

        tokens: List[str] = []
        for raw_tok in raw_tokens:
            for part in re.split(r"[;|&]+", raw_tok):
                if part:
                    tokens.append(part)

        lower_tokens = [t.lower() for t in tokens]

        # 3. Banned CLI tools & suspicious executable check (V2)
        for token in lower_tokens:
            base_tool = Path(token).stem.lower()
            if base_tool in BANNED_TOOLS or token in BANNED_TOOLS:
                violations.append(
                    f"Banned CLI tool detected: '{token}'. Use Python or IDE tools instead."
                )
            elif base_tool in SUSPICIOUS_EXEC_TOOLS or token in SUSPICIOUS_EXEC_TOOLS:
                violations.append(
                    f"Suspicious execution/bypass tool detected: '{token}'."
                )
                is_critical = True

            # Secret token / key exfiltration check (V2)
            if any(sub in token for sub in ("ghp_", "ghs_", "bearer_token", "api_key=")):
                violations.append(f"Inline credential/secret token detected in command: '{token}'")
                is_critical = True

        # 4. Network egress check
        net_allowed = allow_network if allow_network is not None else self.default_allow_network
        if not net_allowed:
            for token in lower_tokens:
                base_tool = Path(token).stem.lower()
                if base_tool in NETWORK_TOOLS or token in NETWORK_TOOLS:
                    violations.append(
                        f"Unauthorized network egress tool detected: '{token}' in network-isolated sandbox."
                    )

        if is_critical:
            return SandboxVerdict(
                allowed=False,
                risk_level=RiskLevel.CRITICAL_BLOCKED,
                violations=violations,
            )
        elif violations:
            return SandboxVerdict(
                allowed=False,
                risk_level=RiskLevel.CAUTION,
                violations=violations,
            )

        return SandboxVerdict(allowed=True, risk_level=RiskLevel.SAFE, violations=[])

    def verify_file_access(self, path: Path | str, mode: str = "r") -> SandboxVerdict:
        target = Path(path)
        violations: List[str] = []

        # 1. Sensitive credential pattern check
        filename = target.name.lower()
        if filename in SENSITIVE_FILENAME_PATTERNS or filename.endswith((".pfx", ".key", ".pem")):
            violations.append(f"Sensitive credential access blocked: '{filename}'")

        # 2. Filesystem containment / jail escape check
        try:
            resolved_target = target.resolve()
            contained = False
            for root in self.allowed_roots:
                try:
                    resolved_target.relative_to(root)
                    contained = True
                    break
                except ValueError:
                    continue

            if not contained:
                violations.append(
                    f"Filesystem jail escape: path '{resolved_target}' is outside allowed roots."
                )
        except Exception as e:
            violations.append(f"Path resolution error: {e}")

        if violations:
            return SandboxVerdict(
                allowed=False,
                risk_level=RiskLevel.CRITICAL_BLOCKED,
                violations=violations,
            )

        return SandboxVerdict(allowed=True, risk_level=RiskLevel.SAFE, violations=[])


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Sandbox Jail Verifier CLI")
    subparsers = parser.add_subparsers(dest="action", required=True)

    cmd_parser = subparsers.add_parser("verify-cmd", help="Verify a command against security policies")
    cmd_parser.add_argument("--command", required=True, help="Command string to inspect")
    cmd_parser.add_argument("--allow-network", action="store_true", help="Allow network tools")

    path_parser = subparsers.add_parser("verify-path", help="Verify a file access path")
    path_parser.add_argument("--path", required=True, help="File path to verify")

    args = parser.parse_args(argv)
    verifier = SandboxJailVerifier()

    if args.action == "verify-cmd":
        verdict = verifier.verify_command(args.command, allow_network=args.allow_network)
        print(json.dumps(verdict.to_dict(), indent=2))
        return 0 if verdict.allowed else 1

    elif args.action == "verify-path":
        verdict = verifier.verify_file_access(args.path)
        print(json.dumps(verdict.to_dict(), indent=2))
        return 0 if verdict.allowed else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
