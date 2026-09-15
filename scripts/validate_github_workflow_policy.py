#!/usr/bin/env python3
"""Fail closed when repository workflows violate Courier GitHub guardrails."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


JOB_PATTERN = re.compile(r"^  ([A-Za-z][A-Za-z0-9_-]*):[ \t]*$", re.MULTILINE)
USES_PATTERN = re.compile(r"^[ \t]*-[ \t]+uses:[ \t]+([^\s#]+)[ \t]*$", re.MULTILINE)
TIMEOUT_PATTERN = re.compile(r"^[ \t]{4}timeout-minutes:[ \t]*([0-9]+)[ \t]*$", re.MULTILINE)
RUNNER_PATTERN = re.compile(r"^[ \t]{4}runs-on:[ \t]*([^\s#]+)[ \t]*$", re.MULTILINE)


def job_blocks(text: str) -> dict[str, str]:
    lines = text.splitlines()
    try:
        jobs_start = next(index for index, line in enumerate(lines) if line == "jobs:")
    except StopIteration:
        return {}
    starts = [
        (index, match.group(1))
        for index, line in enumerate(lines[jobs_start + 1 :], start=jobs_start + 1)
        if (match := JOB_PATTERN.match(line))
    ]
    return {
        name: "\n".join(lines[start : starts[position + 1][0] if position + 1 < len(starts) else len(lines)])
        for position, (start, name) in enumerate(starts)
    }


def contents_permission(block: str) -> str | None:
    match = re.search(r"^[ \t]{6}contents:[ \t]*(read|write|none)[ \t]*$", block, re.MULTILINE)
    return match.group(1) if match else None


def validate_workflow(path: Path, policy: dict[str, object]) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    approved_runners = set(policy["approved_runners"])
    approved_actions = set(policy["approved_actions"])
    maximum_timeout = policy["maximum_timeout_minutes"]
    expected_roles = policy["workflow_roles"].get(path.name)

    if expected_roles is None:
        return [f"{path}: workflow is not explicitly allowlisted"]
    if not re.search(r"^concurrency:\n(?:  .*\n)*?  cancel-in-progress:\s*false\s*$", text, re.MULTILINE):
        errors.append(f"{path}: missing required non-cancelling workflow concurrency")
    if not re.search(r"^permissions:\n[ \t]+contents:[ \t]+read[ \t]*$", text, re.MULTILINE):
        errors.append(f"{path}: global permissions must be contents: read")
    if re.search(r"self-hosted", text, re.IGNORECASE):
        errors.append(f"{path}: self-hosted runners are forbidden")
    if re.search(r"git\s+push\b[^\n]*(?:HEAD:)?main\b", text):
        errors.append(f"{path}: direct main push is forbidden")

    jobs = job_blocks(text)
    if set(jobs) != set(expected_roles):
        errors.append(f"{path}: jobs must exactly match the explicit role allowlist")
    for name, role in expected_roles.items():
        block = jobs.get(name)
        if block is None:
            continue
        timeout_match = TIMEOUT_PATTERN.search(block)
        if timeout_match is None:
            errors.append(f"{path}:{name}: missing timeout-minutes")
        elif not 0 < int(timeout_match.group(1)) <= maximum_timeout:
            errors.append(f"{path}:{name}: timeout-minutes exceeds policy")
        runner_match = RUNNER_PATTERN.search(block)
        if runner_match is None or runner_match.group(1).strip("'\"") not in approved_runners:
            errors.append(f"{path}:{name}: runner is not approved")
        contents = contents_permission(block)
        if role in {"worker", "verifier"} and contents != "read":
            errors.append(f"{path}:{name}: {role} must have contents: read only")
        if role == "proposer":
            if contents != "write" or not re.search(r"^[ \t]{6}pull-requests:[ \t]*write[ \t]*$", block, re.MULTILINE):
                errors.append(f"{path}:{name}: proposer requires only contents and pull-requests write")
            if 'git push origin "HEAD:$PROPOSAL_BRANCH"' not in block or "gh pr create --base main" not in block:
                errors.append(f"{path}:{name}: mutation must be an explicit pull-request proposal")
            for binding in ("TASK_ID:", "ATTEMPT_ID:", "RESULT_PATH:", "VERIFIER_ID:"):
                if binding not in block:
                    errors.append(f"{path}:{name}: missing task/attempt/result/verifier binding")
        for action in USES_PATTERN.findall(block):
            if action not in approved_actions:
                errors.append(f"{path}:{name}: action {action!r} is not explicitly approved")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflows-dir", type=Path, default=Path(".github/workflows"))
    parser.add_argument("--policy", type=Path, default=Path(".github/github-actions-policy.json"))
    args = parser.parse_args()
    try:
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"invalid GitHub Actions policy: {exc}", file=sys.stderr)
        return 1

    errors = [error for path in sorted(args.workflows_dir.glob("*.yml")) for error in validate_workflow(path, policy)]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
