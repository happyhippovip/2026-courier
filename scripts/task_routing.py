#!/usr/bin/env python3
"""Task Routing Engine for Courier Workers and AI Providers.

Evaluates cost-safe, deterministic routing between local platforms (Windows/Mac),
hosted GitHub runners, and AI provider fallback tiers.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def route_task_detailed(task_requirements: dict[str, Any]) -> dict[str, Any]:
    reqs = task_requirements or {}
    target_os = str(reqs.get("target_os") or "").lower()
    requires_mac = bool(reqs.get("requires_mac") or target_os in {"mac", "darwin", "macos"})
    requires_linux = bool(reqs.get("requires_linux") or target_os in {"linux"})
    can_run_local = reqs.get("can_run_local", True)
    needs_hosted = bool(reqs.get("needs_hosted") or reqs.get("requires_cloud"))
    complexity = str(reqs.get("complexity") or "low").lower()

    if requires_mac:
        if can_run_local and os.name != "nt" and sys.platform == "darwin":
            return {
                "route": "LOCAL_MAC",
                "cost_tier": "FREE",
                "target_os": "mac",
                "rationale": "Task requires macOS and running locally on Darwin.",
            }
        return {
            "route": "GITHUB_HOSTED",
            "cost_tier": "CHEAP",
            "target_os": "mac",
            "rationale": "Task requires macOS; delegating to hosted runner.",
        }

    if requires_linux and os.name == "nt":
        return {
            "route": "GITHUB_HOSTED",
            "cost_tier": "CHEAP",
            "target_os": "linux",
            "rationale": "Task requires Linux while local platform is Windows; delegating to hosted runner.",
        }

    if can_run_local and not needs_hosted:
        route_name = "LOCAL_MAC" if sys.platform == "darwin" else "LOCAL_WINDOWS"
        return {
            "route": route_name,
            "cost_tier": "FREE",
            "target_os": "mac" if sys.platform == "darwin" else "windows",
            "rationale": "Deterministic local execution is enabled and resource-safe.",
        }
    elif needs_hosted:
        return {
            "route": "GITHUB_HOSTED",
            "cost_tier": "CHEAP",
            "target_os": target_os or "hosted",
            "rationale": "Explicitly flagged as requiring hosted / cloud infrastructure.",
        }
    elif complexity == "high":
        return {
            "route": "EXPENSIVE_AI_PROVIDER",
            "cost_tier": "EXPENSIVE",
            "target_os": "cloud",
            "rationale": "Task complexity is high; non-local routing to high-capability AI tier.",
        }
    else:
        return {
            "route": "CHEAP_AI_PROVIDER",
            "cost_tier": "CHEAP",
            "target_os": "cloud",
            "rationale": "Task cannot run locally; routing to default cheap AI tier.",
        }


def route_task(task_requirements: dict[str, Any], quiet: bool = False) -> str:
    """Implements cost-safe routing for main workers and hosted fallbacks.

    Order:
    1. Deterministic local (if resource-safe)
    2. Deterministic hosted/GitHub
    3. Cheap AI
    4. Expensive AI
    """
    if not quiet:
        print("Evaluating task routing...")
    decision = route_task_detailed(task_requirements)
    return decision["route"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate task routing for Courier workloads")
    parser.add_argument("--file", help="Path to JSON file with task requirements")
    parser.add_argument("--can-run-local", action="store_true", default=None, help="Force can_run_local=True")
    parser.add_argument("--cannot-run-local", action="store_true", help="Force can_run_local=False")
    parser.add_argument("--needs-hosted", action="store_true", help="Require hosted / cloud runner")
    parser.add_argument("--complexity", choices=["low", "high"], default="low", help="Task complexity")
    parser.add_argument("--target-os", choices=["windows", "linux", "mac", "any"], default="windows", help="Target operating system")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args(argv)

    reqs: dict[str, Any] = {}
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"ERROR: Requirements file not found: {args.file}", file=sys.stderr)
            return 1
        try:
            reqs = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"ERROR: Failed to parse requirements file: {e}", file=sys.stderr)
            return 1

    if args.cannot_run_local:
        reqs["can_run_local"] = False
    elif args.can_run_local is not None:
        reqs["can_run_local"] = True

    if args.needs_hosted:
        reqs["needs_hosted"] = True
    if args.complexity:
        reqs["complexity"] = args.complexity
    if args.target_os and args.target_os != "any":
        reqs["target_os"] = args.target_os

    decision = route_task_detailed(reqs)
    if args.json:
        print(json.dumps(decision, indent=2))
    else:
        print(f"Task assigned to: {decision['route']}")
        print(f"Cost Tier: {decision['cost_tier']}")
        print(f"Rationale: {decision['rationale']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
