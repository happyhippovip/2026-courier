"""Dry-run host setup and list the planned steps (P6).

Inspects the host environment without mutating the filesystem or executing
destructive actions, producing a deterministic, structured plan of setup
steps required to run Courier Symphony.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SetupStep:
    id: str
    title: str
    action: str
    status: str  # "SATISFIED", "PLANNED", "SKIPPED", "BLOCKED"
    required: bool
    details: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SetupPlan:
    platform: str
    python_version: str
    target_home: str
    steps: list[dict[str, Any]]
    is_ready: bool
    summary: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "python_version": self.python_version,
            "target_home": self.target_home,
            "steps": self.steps,
            "is_ready": self.is_ready,
            "summary": self.summary,
        }


def plan_host_setup(
    home: Path | str | None = None,
    mock_platform: str | None = None,
    mock_python_version: tuple[int, int] | None = None,
    mock_git_available: bool | None = None,
) -> SetupPlan:
    """Generate a read-only dry-run setup plan for the host."""
    current_os = mock_platform or platform.system().lower()
    py_ver = mock_python_version or sys.version_info[:2]
    py_ver_str = f"{py_ver[0]}.{py_ver[1]}"

    if home is None:
        home_env = os.environ.get("COURIER_HOME")
        if home_env:
            target_home = Path(home_env).resolve()
        else:
            if current_os == "windows":
                local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
                target_home = Path(local_app_data) / "Courier"
            else:
                target_home = Path.home() / ".courier"
    else:
        target_home = Path(home).resolve()

    steps: list[SetupStep] = []

    # 1. Platform verification
    if current_os in ("darwin", "windows", "linux"):
        steps.append(SetupStep(
            id="verify_platform",
            title="Verify Operating System",
            action=f"Recognize host platform ({current_os})",
            status="SATISFIED",
            required=True,
            details=f"Supported host operating system: {current_os}",
        ))
    else:
        steps.append(SetupStep(
            id="verify_platform",
            title="Verify Operating System",
            action=f"Recognize host platform ({current_os})",
            status="BLOCKED",
            required=True,
            details=f"Unsupported operating system: {current_os}",
        ))

    # 2. Python runtime version check
    if py_ver >= (3, 9):
        steps.append(SetupStep(
            id="verify_python_version",
            title="Verify Python Version",
            action=f"Check Python version >= 3.9 (current: {py_ver_str})",
            status="SATISFIED",
            required=True,
            details=f"Python {py_ver_str} meets runtime requirements.",
        ))
    else:
        steps.append(SetupStep(
            id="verify_python_version",
            title="Verify Python Version",
            action=f"Check Python version >= 3.9 (current: {py_ver_str})",
            status="BLOCKED",
            required=True,
            details=f"Python {py_ver_str} is below the required 3.9 minimum.",
        ))

    # 3. Git toolchain check
    has_git = (shutil.which("git") is not None) if mock_git_available is None else mock_git_available
    if has_git:
        steps.append(SetupStep(
            id="check_git_available",
            title="Check Git Toolchain",
            action="Find git binary on system PATH",
            status="SATISFIED",
            required=True,
            details="Git is installed and available on PATH.",
        ))
    else:
        steps.append(SetupStep(
            id="check_git_available",
            title="Check Git Toolchain",
            action="Find git binary on system PATH",
            status="BLOCKED",
            required=True,
            details="Git binary was not found on PATH.",
        ))

    # 4. Target home directory existence
    if target_home.is_dir():
        steps.append(SetupStep(
            id="ensure_courier_home",
            title="Ensure Courier Home Directory",
            action=f"Create base directory at {target_home}",
            status="SATISFIED",
            required=True,
            details=f"Home directory already exists at {target_home}",
        ))
    else:
        steps.append(SetupStep(
            id="ensure_courier_home",
            title="Ensure Courier Home Directory",
            action=f"Create base directory at {target_home}",
            status="PLANNED",
            required=True,
            details=f"Directory will be created at {target_home}",
        ))

    # 5. Required subdirectories layout
    required_subdirs = ["run", "logs", "delivered_articles"]
    for subdir in required_subdirs:
        subpath = target_home / subdir
        if subpath.is_dir():
            steps.append(SetupStep(
                id=f"ensure_subdir_{subdir}",
                title=f"Ensure Subdirectory '{subdir}'",
                action=f"Create directory {subpath}",
                status="SATISFIED",
                required=True,
                details=f"Subdirectory exists: {subpath}",
            ))
        else:
            steps.append(SetupStep(
                id=f"ensure_subdir_{subdir}",
                title=f"Ensure Subdirectory '{subdir}'",
                action=f"Create directory {subpath}",
                status="PLANNED",
                required=True,
                details=f"Subdirectory will be created: {subpath}",
            ))

    # 6. Service / launcher permissions check
    steps.append(SetupStep(
        id="check_permissions_and_tokens",
        title="Check Security & Token Layout",
        action="Ensure permissions on <home>/run and controller token file",
        status="PLANNED" if not (target_home / "run" / "controller.token").exists() else "SATISFIED",
        required=True,
        details="Access token is generated once on initial serve.",
    ))

    # Summary calculations
    step_dicts = [s.to_dict() for s in steps]
    counts = {"SATISFIED": 0, "PLANNED": 0, "BLOCKED": 0, "SKIPPED": 0}
    for s in steps:
        counts[s.status] = counts.get(s.status, 0) + 1

    is_ready = counts["BLOCKED"] == 0

    return SetupPlan(
        platform=current_os,
        python_version=py_ver_str,
        target_home=str(target_home),
        steps=step_dicts,
        is_ready=is_ready,
        summary=counts,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Courier Host Setup Dry-Run (P6)")
    parser.add_argument("--home", type=Path, default=None, help="Target COURIER_HOME directory")
    parser.add_argument("--json", action="store_true", help="Output plan as JSON")
    args = parser.parse_args(argv)

    plan = plan_host_setup(home=args.home)

    if args.json:
        print(json.dumps(plan.to_dict(), indent=2))
    else:
        print(f"=== Courier Host Setup Dry-Run ===")
        print(f"Platform:       {plan.platform}")
        print(f"Python Version: {plan.python_version}")
        print(f"Target Home:    {plan.target_home}")
        print(f"Ready to run:   {'YES' if plan.is_ready else 'NO (Blocked steps present)'}\n")
        print("Planned Steps:")
        for idx, step in enumerate(plan.steps, start=1):
            mark = "[✓]" if step["status"] == "SATISFIED" else "[ ]" if step["status"] == "PLANNED" else "[!]"
            print(f"  {idx}. {mark} {step['title']} ({step['status']}): {step['action']}")
            if step.get("details"):
                print(f"     -> {step['details']}")

    return 0 if plan.is_ready else 1


if __name__ == "__main__":
    sys.exit(main())
