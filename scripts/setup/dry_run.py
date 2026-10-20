"""Dry-run host setup and list planned execution steps (P6).

Simulates the host setup process (Windows, Darwin/macOS, Linux) without performing
any mutations to the host environment, files, registry, or service managers.
Checks prerequisites, credentials, paths, and outputs a structured execution plan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from courier_core.events import canonical_json


@dataclass(frozen=True)
class SetupStep:
    step_id: int
    action: str  # "CREATE_DIRECTORY", "WRITE_CONFIG", "REGISTER_TASK", "GENERATE_LAUNCHD_PLIST", "LOAD_LAUNCHCTL", "GENERATE_SYSTEMD_UNIT", "ENABLE_SYSTEMD_SERVICE"
    target: str
    description: str
    requires_elevation: bool
    status: str = "PLANNED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "target": self.target,
            "description": self.description,
            "requires_elevation": self.requires_elevation,
            "status": self.status,
        }


@dataclass(frozen=True)
class SetupPlan:
    host_os: str
    hostname: str
    can_proceed: bool
    missing_prereqs: list[str]
    steps: list[SetupStep]
    plan_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "host_os": self.host_os,
            "hostname": self.hostname,
            "can_proceed": self.can_proceed,
            "missing_prereqs": self.missing_prereqs,
            "steps": [s.to_dict() for s in self.steps],
            "plan_sha256": self.plan_sha256,
        }


def plan_host_setup(
    target_dir: Path | str | None = None,
    os_override: str | None = None,
    env: Mapping[str, str] | None = None,
) -> SetupPlan:
    """Generate a dry-run plan for host setup without mutating disk or system services."""
    env_map = env if env is not None else os.environ
    effective_os = (os_override or platform.system()).lower()
    target_path = Path(target_dir).resolve() if target_dir else Path.cwd().resolve()
    hostname = platform.node() or "localhost"

    # Check required credentials without storing cleartext
    missing_prereqs: list[str] = []
    api_key = env_map.get("COURIER_API_KEY", "").strip()
    verifier_key = env_map.get("COURIER_VERIFIER_API_KEY", "").strip()

    if not api_key:
        missing_prereqs.append("COURIER_API_KEY")
    if not verifier_key:
        missing_prereqs.append("COURIER_VERIFIER_API_KEY")

    steps: list[SetupStep] = []
    step_counter = 1

    if effective_os in ("windows", "win32", "nt"):
        # Windows Planned Steps
        steps.append(
            SetupStep(
                step_id=step_counter,
                action="CREATE_DIRECTORY",
                target=str(target_path / "logs"),
                description="Create logs directory for runner and verifier output",
                requires_elevation=False,
            )
        )
        step_counter += 1

        steps.append(
            SetupStep(
                step_id=step_counter,
                action="CREATE_DIRECTORY",
                target=str(target_path / "run"),
                description="Create run directory for controller token and IPC locks",
                requires_elevation=False,
            )
        )
        step_counter += 1

        steps.append(
            SetupStep(
                step_id=step_counter,
                action="WRITE_CONFIG",
                target=str(target_path / "config.json"),
                description="Write sanitized worker configuration (API key injected via environment)",
                requires_elevation=False,
            )
        )
        step_counter += 1

        steps.append(
            SetupStep(
                step_id=step_counter,
                action="REGISTER_TASK",
                target="CourierWorker",
                description="Register Windows Scheduled Task or background service under user profile",
                requires_elevation=False,
            )
        )
        step_counter += 1

    elif effective_os in ("darwin", "mac", "macos"):
        # macOS Planned Steps
        steps.append(
            SetupStep(
                step_id=step_counter,
                action="CREATE_DIRECTORY",
                target=str(target_path / "logs"),
                description="Create logs directory for launchd stdout and stderr",
                requires_elevation=False,
            )
        )
        step_counter += 1

        plist_target = "~/Library/LaunchAgents/com.courier.server.plist"
        steps.append(
            SetupStep(
                step_id=step_counter,
                action="GENERATE_LAUNCHD_PLIST",
                target=plist_target,
                description="Generate LaunchAgent property list for supervisor process",
                requires_elevation=False,
            )
        )
        step_counter += 1

        steps.append(
            SetupStep(
                step_id=step_counter,
                action="LOAD_LAUNCHCTL",
                target=plist_target,
                description="Load LaunchAgent service into user launchd session",
                requires_elevation=False,
            )
        )
        step_counter += 1

    else:
        # Linux / Default Planned Steps
        steps.append(
            SetupStep(
                step_id=step_counter,
                action="CREATE_DIRECTORY",
                target=str(target_path / "logs"),
                description="Create logs directory for supervisor and worker output",
                requires_elevation=False,
            )
        )
        step_counter += 1

        unit_target = "~/.config/systemd/user/courier-worker.service"
        steps.append(
            SetupStep(
                step_id=step_counter,
                action="GENERATE_SYSTEMD_UNIT",
                target=unit_target,
                description="Generate user systemd service unit file",
                requires_elevation=False,
            )
        )
        step_counter += 1

        steps.append(
            SetupStep(
                step_id=step_counter,
                action="ENABLE_SYSTEMD_SERVICE",
                target="courier-worker.service",
                description="Enable and start user systemd service",
                requires_elevation=False,
            )
        )
        step_counter += 1

    can_proceed = len(missing_prereqs) == 0

    # Deterministic SHA-256 over canonical JSON of the steps and plan
    serialized_steps = [s.to_dict() for s in steps]
    canonical_repr = canonical_json({
        "host_os": effective_os,
        "target_dir": str(target_path).replace("\\", "/"),
        "steps": serialized_steps,
    })
    plan_sha256 = hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()

    return SetupPlan(
        host_os=effective_os,
        hostname=hostname,
        can_proceed=can_proceed,
        missing_prereqs=missing_prereqs,
        steps=steps,
        plan_sha256=plan_sha256,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for host setup dry-run."""
    parser = argparse.ArgumentParser(description="Dry-run Courier host setup and list planned steps.")
    parser.add_argument("--target-dir", type=str, help="Target installation directory")
    parser.add_argument("--os", type=str, help="Override target OS (windows, darwin, linux)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    args = parser.parse_args(argv)
    plan = plan_host_setup(target_dir=args.target_dir, os_override=args.os)

    if args.json:
        print(json.dumps(plan.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"=== Courier Host Setup Dry-Run ({plan.host_os.upper()}) ===")
        print(f"Hostname:    {plan.hostname}")
        print(f"Can Proceed: {plan.can_proceed}")
        if plan.missing_prereqs:
            print(f"Missing:     {', '.join(plan.missing_prereqs)}")
        print(f"Plan Digest: {plan.plan_sha256}")
        print("\nPlanned Steps:")
        for step in plan.steps:
            elev = " [REQUIRES ELEVATION]" if step.requires_elevation else ""
            print(f"  {step.step_id}. [{step.action}] {step.target}{elev}")
            print(f"     {step.description}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
