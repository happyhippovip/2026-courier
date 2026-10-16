"""Verifier receipt for a PR head.

A receipt is acceptance only when every field is present and the checkout
agrees. ``source_sha`` uses the same rule as the provenance contract in
PR #602: 40 lowercase hex digits, equal to ``git rev-parse HEAD``.

``verify`` never returns RESULT_ACCEPTED for a SHA mismatch, a changed
artifact, a non-zero exit, a missing field, a skip treated as success, or an
unknown state. It does not report VERIFIED.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "courier.verifier_receipt/v1"
RESULT_ACCEPTED = "RESULT_ACCEPTED"
RESULT_REJECTED = "RESULT_REJECTED"
# Same shape as scripts/integration_contract.py on fix/provenance-binding (#602).
_SOURCE_SHA = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SKIP_RESULTS = frozenset({"SKIP", "SKIPPED", "SKIPPED_AS_SUCCESS"})
_REQUIRED = (
    "schema",
    "result",
    "pr_head_sha",
    "source_sha",
    "artifacts",
    "test_command",
    "exit_code",
    "skipped",
    "timestamp",
    "host",
    "platform",
)
_ALLOWED = frozenset(_REQUIRED) | {"owner"}


def host_platform() -> str:
    """The machine actually running this process, same mapping as PR #602."""
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform == "linux":
        return "linux"
    return sys.platform


def _git(repo: Path, *args: str, text: bool = True) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=text,
            check=False,
        )
    except OSError:
        return None


def checkout_source_sha(repo: Path) -> str | None:
    """Full git HEAD of ``repo``, or None when it is not a 40-hex commit."""
    proc = _git(repo, "rev-parse", "HEAD")
    if proc is None or proc.returncode != 0:
        return None
    sha = (proc.stdout or "").strip()
    if _SOURCE_SHA.fullmatch(sha):
        return sha
    return None


def _blob_bytes(repo: Path, revision: str, rel: str) -> bytes | None:
    proc = _git(repo, "show", f"{revision}:{rel}", text=False)
    if proc is None or proc.returncode != 0:
        return None
    return proc.stdout


def _safe_rel(path: str) -> str | None:
    if not isinstance(path, str) or not path.strip():
        return None
    if path.startswith(("/", "\\")) or "\\" in path:
        return None
    parts = Path(path).parts
    if not parts or ".." in parts or Path(path).is_absolute():
        return None
    return path


def _reject(reason: str) -> dict:
    return {"result": RESULT_REJECTED, "reason": reason}


def _aware_timestamp(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return parsed.tzinfo is not None


def _matches_blob_hash(work_bytes: bytes, expected_hash: str) -> bool:
    if hashlib.sha256(work_bytes).hexdigest() == expected_hash:
        return True
    if sys.platform == "win32" and hashlib.sha256(work_bytes.replace(b"\r\n", b"\n")).hexdigest() == expected_hash:
        return True
    return False


def issue(
    repo: str | Path,
    *,
    test_command: str,
    exit_code: int,
    skipped: int,
    artifacts: list[str],
    now: datetime | None = None,
    owner: str | None = None,
) -> dict:
    """Record a run. RESULT_ACCEPTED only for exit 0, zero skips, and a clean checkout."""
    repo = Path(repo)
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    head = checkout_source_sha(repo)
    recorded = []
    clean = True
    for rel in artifacts:
        safe = _safe_rel(rel)
        blob = _blob_bytes(repo, "HEAD", safe) if safe and head else None
        work = (repo / safe) if safe else None
        if blob is None or work is None or not work.is_file():
            clean = False
            continue
        blob_hash = hashlib.sha256(blob).hexdigest()
        if not _matches_blob_hash(work.read_bytes(), blob_hash):
            clean = False
        recorded.append({"path": safe, "sha256": blob_hash})
    accepted = (
        bool(head)
        and clean
        and len(recorded) == len(artifacts)
        and recorded
        and exit_code == 0
        and skipped == 0
        and isinstance(test_command, str)
        and bool(test_command.strip())
    )
    receipt = {
        "schema": SCHEMA,
        "result": RESULT_ACCEPTED if accepted else RESULT_REJECTED,
        "pr_head_sha": head or "",
        "source_sha": head or "",
        "artifacts": recorded,
        "test_command": test_command,
        "exit_code": exit_code,
        "skipped": skipped,
        "timestamp": moment.isoformat(),
        "host": socket.gethostname(),
        "platform": host_platform(),
    }
    if owner:
        receipt["owner"] = owner
    return receipt


def verify(receipt: dict, repo: str | Path, *, revision: str | None = None) -> dict:
    """Accept the receipt only when the checkout and the run both agree."""
    repo = Path(repo)
    if not isinstance(receipt, dict):
        return _reject("unknown_state")
    if any(key not in receipt for key in _REQUIRED):
        return _reject("missing_field")
    if set(receipt) - _ALLOWED:
        return _reject("unknown_state")

    result = receipt["result"]
    if result in _SKIP_RESULTS:
        return _reject("skip_as_success")
    if result not in (RESULT_ACCEPTED, RESULT_REJECTED):
        return _reject("unknown_state")
    if receipt["schema"] != SCHEMA:
        return _reject("unknown_state")
    if not isinstance(receipt["test_command"], str) or not receipt["test_command"].strip():
        return _reject("missing_field")
    if isinstance(receipt["exit_code"], bool) or not isinstance(receipt["exit_code"], int):
        return _reject("unknown_state")
    if isinstance(receipt["skipped"], bool) or not isinstance(receipt["skipped"], int) or receipt["skipped"] < 0:
        return _reject("unknown_state")
    if not _aware_timestamp(receipt["timestamp"]):
        return _reject("unknown_state")
    if not isinstance(receipt["host"], str) or not receipt["host"].strip():
        return _reject("missing_field")
    if receipt["host"] != socket.gethostname():
        return _reject("unknown_state")
    if receipt["platform"] != host_platform():
        return _reject("unknown_state")
    if "owner" in receipt and (not isinstance(receipt["owner"], str) or not receipt["owner"].strip()):
        return _reject("unknown_state")

    artifacts = receipt["artifacts"]
    if not isinstance(artifacts, list) or not artifacts:
        return _reject("missing_field")
    seen: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            return _reject("unknown_state")
        rel = _safe_rel(item["path"])
        if rel is None or rel in seen or not _SHA256.fullmatch(item["sha256"]):
            return _reject("artifact_hash")
        seen.add(rel)

    attested = receipt["pr_head_sha"]
    source = receipt["source_sha"]
    if not _SOURCE_SHA.fullmatch(str(attested)) or not _SOURCE_SHA.fullmatch(str(source)) or attested != source:
        return _reject("sha_mismatch")
    if revision is None:
        if checkout_source_sha(repo) != attested:
            return _reject("sha_mismatch")
        git_rev = "HEAD"
    else:
        if not _SOURCE_SHA.fullmatch(revision) or revision != attested:
            return _reject("sha_mismatch")
        if checkout_source_sha_of(repo, revision) != attested:
            return _reject("sha_mismatch")
        git_rev = revision

    for item in artifacts:
        blob = _blob_bytes(repo, git_rev, item["path"])
        if blob is None or hashlib.sha256(blob).hexdigest() != item["sha256"]:
            return _reject("artifact_hash")
        if revision is None:
            work = repo / item["path"]
            if not work.is_file() or not _matches_blob_hash(work.read_bytes(), item["sha256"]):
                return _reject("artifact_hash")

    if result == RESULT_ACCEPTED and receipt["skipped"] != 0:
        return _reject("skip_as_success")
    if receipt["exit_code"] != 0:
        return _reject("exit_nonzero")
    if result != RESULT_ACCEPTED:
        return _reject("unknown_state")
    return {"result": RESULT_ACCEPTED, "reason": ""}


def checkout_source_sha_of(repo: Path, revision: str) -> str | None:
    proc = _git(repo, "rev-parse", "--verify", f"{revision}^{{commit}}")
    if proc is None or proc.returncode != 0:
        return None
    sha = (proc.stdout or "").strip()
    if _SOURCE_SHA.fullmatch(sha):
        return sha
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Issue or verify a Courier verifier receipt.")
    sub = parser.add_subparsers(dest="command", required=True)

    issue_parser = sub.add_parser("issue", help="write a receipt for this checkout")
    issue_parser.add_argument("--repo", default=".")
    issue_parser.add_argument("--command", required=True)
    issue_parser.add_argument("--artifact", action="append", required=True)
    issue_parser.add_argument("--out")
    issue_parser.add_argument("--exit-code", type=int)
    issue_parser.add_argument("--skipped", type=int)
    issue_parser.add_argument("--run", action="store_true")
    issue_parser.add_argument("--owner", default="")

    verify_parser = sub.add_parser("verify", help="accept the receipt only if the checkout matches")
    verify_parser.add_argument("receipt")
    verify_parser.add_argument("--repo", default=".")
    verify_parser.add_argument("--revision", default="")

    args = parser.parse_args(argv)
    if args.command == "verify":
        try:
            receipt = json.loads(Path(args.receipt).read_text())
        except (OSError, json.JSONDecodeError):
            print(json.dumps(_reject("unknown_state")))
            return 1
        check = verify(receipt, Path(args.repo), revision=args.revision or None)
        print(json.dumps(check))
        return 0 if check["result"] == RESULT_ACCEPTED else 1

    exit_code = args.exit_code
    skipped = args.skipped
    if args.run:
        proc = subprocess.run(
            args.command,
            shell=True,
            cwd=args.repo,
            capture_output=True,
            text=True,
        )
        exit_code = proc.returncode
        if skipped is None:
            skipped = _pytest_skipped(proc.stdout + "\n" + proc.stderr)
            if skipped is None:
                print(json.dumps(_reject("unknown_state")))
                return 2
    if exit_code is None or skipped is None:
        print(json.dumps(_reject("missing_field")))
        return 2
    receipt = issue(
        args.repo,
        test_command=args.command,
        exit_code=exit_code,
        skipped=skipped,
        artifacts=args.artifact,
        owner=args.owner or None,
    )
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text)
    print(text, end="")
    return 0 if receipt["result"] == RESULT_ACCEPTED else 1


def _pytest_skipped(output: str) -> int | None:
    """Read a pytest summary. None when the output does not say how many skipped."""
    match = None
    for line in output.splitlines():
        if re.search(r"\d+ .+\bin [\d.]+s\s*$", line):
            match = line
    if match is None:
        return None
    found = re.search(r"(\d+) skipped", match)
    return int(found.group(1)) if found else 0
