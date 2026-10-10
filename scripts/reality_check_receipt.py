#!/usr/bin/env python3
"""Repo Reality Check Proof Card and Receipt Verification Engine.

Generates and cryptographically verifies tamper-evident proof cards for
Repo Reality Check markdown and JSON audit reports.

Usage:
    python -m scripts.reality_check_receipt make <report_json_or_dir> [--out <receipt_file>] [--order-id <id>]
    python -m scripts.reality_check_receipt verify <receipt_file> <report_json_or_dir>
    python -m scripts.reality_check_receipt card <receipt_file>
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any
import uuid

MAX_REPORT_BYTES = 5 * 1024 * 1024  # 5 MB cap
MAX_RECEIPT_BYTES = 1 * 1024 * 1024  # 1 MB cap
DEFAULT_VERIFIER = "courier-audit-l4"
RECEIPT_VERSION = "1.0"
RECEIPT_TYPE = "REPO_REALITY_PROOF_CARD"


class ReceiptError(Exception):
    """Base exception for reality check receipt operations."""


def compute_reality_score(high: int, medium: int, low: int) -> int:
    """Calculates 0-100 reality score from severity counts."""
    penalty = (high * 15) + (medium * 5) + (low * 1)
    return max(0, min(100, 100 - penalty))


def compute_proof_signature(payload: dict[str, Any]) -> str:
    """SHA-256 over deterministic canonical JSON of unsigned receipt payload."""
    clean = {k: v for k, v in payload.items() if k != "proof_signature"}
    canonical = json.dumps(clean, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def resolve_report_path(path_str: str | os.PathLike) -> Path:
    """Resolves report.json whether given a direct file or directory."""
    path = Path(path_str).resolve()
    if path.is_dir():
        candidate = path / "report.json"
        if candidate.is_file():
            return candidate
        raise ReceiptError(f"report.json not found in directory: {path}")
    if path.is_file():
        return path
    raise ReceiptError(f"report file not found: {path}")


def read_report_data(report_path: Path) -> tuple[dict[str, Any], str, int]:
    """Reads and validates report.json, returning (data, sha256_hex, byte_size)."""
    if report_path.is_symlink():
        raise ReceiptError("symlinks not permitted for report files")
    try:
        size = report_path.stat().st_size
    except OSError as exc:
        raise ReceiptError(f"cannot stat report file: {exc}") from exc
    if size <= 0 or size > MAX_REPORT_BYTES:
        raise ReceiptError(f"report file size ({size} bytes) outside bounds (1 .. {MAX_REPORT_BYTES})")

    try:
        raw_bytes = report_path.read_bytes()
    except OSError as exc:
        raise ReceiptError(f"cannot read report file: {exc}") from exc

    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptError(f"invalid JSON in report file: {exc}") from exc

    if not isinstance(data, dict):
        raise ReceiptError("report root must be a JSON object")

    required = ("repository", "sha", "tool", "files_scanned", "summary", "digest")
    for req in required:
        if req not in data:
            raise ReceiptError(f"report missing required field: {req}")

    summary = data["summary"]
    if not isinstance(summary, dict) or not all(k in summary for k in ("high", "medium", "low")):
        raise ReceiptError("report summary must contain high, medium, and low integer counts")

    report_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    return data, report_sha256, len(raw_bytes)


def create_proof_card(
    report_path_or_dir: str | os.PathLike,
    order_id: str | None = None,
    verifier_identity: str = DEFAULT_VERIFIER,
    moment: datetime | None = None,
) -> dict[str, Any]:
    """Generates a signed, verifiable Proof Card from a report file."""
    path = resolve_report_path(report_path_or_dir)
    data, report_sha256, report_bytes = read_report_data(path)

    sha = str(data.get("sha") or "unknown")
    short_sha = sha[:8] if len(sha) >= 8 else sha
    token = uuid.uuid4().hex[:12]
    receipt_id = f"rcpt-reality-{short_sha}-{token}"

    summary = data["summary"]
    high = int(summary.get("high", 0))
    medium = int(summary.get("medium", 0))
    low = int(summary.get("low", 0))
    score = compute_reality_score(high, medium, low)
    clean_verdict = (high == 0)

    now = moment or datetime.now(timezone.utc)
    timestamp = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    card = {
        "receipt_id": receipt_id,
        "version": RECEIPT_VERSION,
        "receipt_type": RECEIPT_TYPE,
        "goal": "repo-reality-check",
        "order_id": order_id or "adhoc",
        "repository": str(data["repository"]),
        "commit_sha": sha,
        "tool_version": str(data["tool"]),
        "files_scanned": int(data["files_scanned"]),
        "summary": {
            "high": high,
            "medium": medium,
            "low": low,
        },
        "score": score,
        "clean_verdict": clean_verdict,
        "artifact_digest": str(data["digest"]),
        "report_sha256": report_sha256,
        "report_bytes": report_bytes,
        "verified_at": timestamp,
        "verifier_identity": verifier_identity,
    }

    card["proof_signature"] = compute_proof_signature(card)
    return card


def verify_proof_card(
    receipt_path: str | os.PathLike,
    report_path_or_dir: str | os.PathLike,
) -> dict[str, Any]:
    """Verifies that a Proof Card receipt matches the given report exactly."""
    r_path = Path(receipt_path).resolve()
    if r_path.is_symlink() or not r_path.is_file():
        raise ReceiptError("receipt must be an existing regular file (symlinks forbidden)")

    size = r_path.stat().st_size
    if size <= 0 or size > MAX_RECEIPT_BYTES:
        raise ReceiptError(f"receipt size ({size} bytes) outside allowable bounds")

    try:
        receipt = json.loads(r_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptError(f"receipt contains invalid JSON: {exc}") from exc

    if not isinstance(receipt, dict):
        raise ReceiptError("receipt root must be a JSON dictionary")

    sig = receipt.get("proof_signature")
    if not isinstance(sig, str) or len(sig) != 64:
        raise ReceiptError("receipt missing valid 64-char proof_signature")

    expected_sig = compute_proof_signature(receipt)
    if sig != expected_sig:
        raise ReceiptError("proof_signature mismatch: receipt has been tampered with")

    rep_path = resolve_report_path(report_path_or_dir)
    data, report_sha256, report_bytes = read_report_data(rep_path)

    if receipt.get("report_sha256") != report_sha256:
        raise ReceiptError(
            f"report_sha256 mismatch: receipt claims {receipt.get('report_sha256')}, "
            f"actual report is {report_sha256}"
        )

    if receipt.get("report_bytes") != report_bytes:
        raise ReceiptError(
            f"report_bytes mismatch: receipt claims {receipt.get('report_bytes')}, "
            f"actual is {report_bytes}"
        )

    if receipt.get("commit_sha") != data.get("sha"):
        raise ReceiptError(
            f"commit_sha mismatch: receipt claims {receipt.get('commit_sha')}, "
            f"report has {data.get('sha')}"
        )

    if receipt.get("artifact_digest") != data.get("digest"):
        raise ReceiptError(
            f"artifact_digest mismatch: receipt claims {receipt.get('artifact_digest')}, "
            f"report has {data.get('digest')}"
        )

    if receipt.get("repository") != data.get("repository"):
        raise ReceiptError("repository name mismatch between receipt and report")

    return {
        "ok": True,
        "receipt_id": receipt["receipt_id"],
        "repository": receipt["repository"],
        "commit_sha": receipt["commit_sha"],
        "score": receipt["score"],
        "clean_verdict": receipt["clean_verdict"],
        "verified_at": receipt["verified_at"],
    }


def render_markdown_card(receipt: dict[str, Any]) -> str:
    """Renders an ASCII/Markdown Proof Card badge suitable for embedding."""
    badge = "CLEAN PASS" if receipt.get("clean_verdict") else "REVIEW REQUIRED"
    score = receipt.get("score", 0)
    lines = [
        "```",
        "┌─────────────────────────────────────────────────────────────────┐",
        f"│ COURIER SYMPHONY — REPO REALITY CHECK PROOF CARD                │",
        "├─────────────────────────────────────────────────────────────────┤",
        f"│ Receipt ID: {receipt.get('receipt_id', ''):<51} │",
        f"│ Repository: {receipt.get('repository', ''):<51} │",
        f"│ Commit SHA: {receipt.get('commit_sha', ''):<51} │",
        f"│ Reality Score: {score}/100 [{badge}]".ljust(66) + "│",
        "├─────────────────────────────────────────────────────────────────┤",
        f"│ Scanned Files: {receipt.get('files_scanned', 0):<48} │",
        f"│ High Risks: {receipt.get('summary', {}).get('high', 0):<51} │",
        f"│ Medium Risks: {receipt.get('summary', {}).get('medium', 0):<49} │",
        f"│ Low Risks: {receipt.get('summary', {}).get('low', 0):<52} │",
        "├─────────────────────────────────────────────────────────────────┤",
        f"│ Report SHA256: {receipt.get('report_sha256', '')[:48]:<48} │",
        f"│ Verified At:   {receipt.get('verified_at', ''):<48} │",
        f"│ Signature:     {receipt.get('proof_signature', '')[:48]:<48} │",
        "└─────────────────────────────────────────────────────────────────┘",
        "```",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.reality_check_receipt",
        description="Repo Reality Check Proof Card generator and verification tool.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    make_cmd = sub.add_parser("make", help="Generate a proof card receipt from a report")
    make_cmd.add_argument("report", help="Path to report.json or directory containing it")
    make_cmd.add_argument("--out", "-o", help="Output path for receipt JSON (default: stdout)")
    make_cmd.add_argument("--order-id", default=None, help="Associated order ID")
    make_cmd.add_argument("--verifier", default=DEFAULT_VERIFIER, help="Verifier identity string")

    verify_cmd = sub.add_parser("verify", help="Verify a proof card against a report")
    verify_cmd.add_argument("receipt", help="Path to receipt JSON file")
    verify_cmd.add_argument("report", help="Path to report.json or directory containing it")

    card_cmd = sub.add_parser("card", help="Render an ASCII proof card from a receipt file")
    card_cmd.add_argument("receipt", help="Path to receipt JSON file")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "make":
            card = create_proof_card(
                report_path_or_dir=args.report,
                order_id=args.order_id,
                verifier_identity=args.verifier,
            )
            out_str = json.dumps(card, indent=2)
            if args.out:
                out_path = Path(args.out)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(out_str, encoding="utf-8")
                print(f"WROTE: {out_path} ({card['receipt_id']})")
            else:
                print(out_str)
            return 0

        elif args.cmd == "verify":
            res = verify_proof_card(args.receipt, args.report)
            print(f"VERIFIED: Proof Card matches report ({res['receipt_id']}, score={res['score']}/100)")
            return 0

        elif args.cmd == "card":
            receipt_data = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
            print(render_markdown_card(receipt_data))
            return 0

        else:
            parser.error(f"unknown command: {args.cmd}")
            return 2

    except ReceiptError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
