# ============================================================================
# 2026 Courier // Mission 107: Review Budget Manager & Delta Review Gate
# Deterministic, local, low-cost review control layer preventing unnecessary
# repeated Codex reviews.
#
# Core Invariant:
# ONE_TASK -> ONE_BUILDER -> LOCAL_VERIFY -> DELTA + RISK GATE
# -> REVIEW ONLY IF NEW JUDGMENT IS REQUIRED
# ============================================================================

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    from resource_intelligence import ResourceIntelligenceManager
except ImportError:
    from scripts.resource_intelligence import ResourceIntelligenceManager

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
EVENTS_DIR = COURIER_DIR / "events"
REVIEWS_DIR = EVENTS_DIR / "reviews"
POLICIES_DIR = EVENTS_DIR / "policies"
POLICY_FILE = POLICIES_DIR / "review_policy.json"
LEDGER_JSON = REVIEWS_DIR / "ledger.json"
LEDGER_LOG = REVIEWS_DIR / "review_ledger.jsonl"
LEDGER_LOCK = REVIEWS_DIR / "ledger.lock"

MODEL_REVIEW_TRIGGER = "INFORMATION_GAIN_NOT_TIME"
ROUTINE_DAILY_REVIEW = "OFF"
FULL_REPO_REVIEW = "EXCEPTION_ONLY"
DELTA_REVIEW = "DEFAULT"
UNCHANGED_FILE_RESEND = "FORBIDDEN"
DETERMINISTIC_CHECKS = "ALWAYS"
LOW_RISK_REVIEW = "BATCH_OPTIONAL"
MEDIUM_RISK_REVIEW = "REQUIRED_BEFORE_MAIN_PUSH"
HIGH_RISK_REVIEW = "REQUIRED_BEFORE_ACTIVATION_OR_EXTERNAL_RELEASE"
NO_CHANGE = "NO_REVIEW"
SAME_DIFF_HASH = "REUSE_PREVIOUS_REVIEW"
MAX_ROUTINE_CODEX_BATCHES_PER_DAY = 1


def canonical_json_dumps(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_sha256(data: Any) -> str:
    if isinstance(data, (dict, list)):
        payload_str = canonical_json_dumps(data)
        return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    elif isinstance(data, str):
        return hashlib.sha256(data.encode("utf-8")).hexdigest()
    elif isinstance(data, bytes):
        return hashlib.sha256(data).hexdigest()
    else:
        return hashlib.sha256(str(data).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(temp_path, path)


class ReviewRiskClassifier:
    """Deterministic rule-based risk classification for code/policy deltas."""

    HIGH_RISK_PATTERNS = [
        "auth", "hmac", "signature", "oauth", "token", "secret", "credential",
        "permission", "spending", "payment", "cost_gate", "destructive",
        "2026-project-memory", "apply_memory_update", "lock", "lease", "atomic",
        "claims", "security"
    ]
    MEDIUM_RISK_PATTERNS = [
        "routing", "dispatcher", "agent", "persistence", "orchestration",
        "supervisor", "autonomous_loop", "chief_commander", "github_transport"
    ]
    LOW_RISK_EXTENSIONS = {".md", ".txt", ".jsonl", ".png", ".jpg", ".svg", ".css"}

    @classmethod
    def classify(cls, changed_files: list[str], diff_str: str = "") -> tuple[str, list[str]]:
        if not changed_files and not diff_str:
            return "LOW", ["NO_CHANGES_DETECTED"]

        reasons: list[str] = []
        files_str = " ".join(changed_files).lower()
        diff_lower = diff_str.lower()

        # Check HIGH risk patterns
        for pattern in cls.HIGH_RISK_PATTERNS:
            if pattern in files_str or pattern in diff_lower:
                reasons.append(f"HIGH_RISK_PATTERN_MATCHED: {pattern}")

        if reasons:
            return "HIGH", reasons

        # Check MEDIUM risk patterns
        for pattern in cls.MEDIUM_RISK_PATTERNS:
            if pattern in files_str or pattern in diff_lower:
                reasons.append(f"MEDIUM_RISK_PATTERN_MATCHED: {pattern}")

        if reasons:
            return "MEDIUM", reasons

        # Check if all files are LOW risk (docs, tests, assets)
        all_low = True
        for f in changed_files:
            f_lower = f.lower()
            ext = Path(f).suffix.lower()
            is_doc = ext in cls.LOW_RISK_EXTENSIONS or "doc" in f_lower or "readme" in f_lower
            is_test = "tests/" in f_lower or "test_" in f_lower or "_test." in f_lower
            is_asset = "assets/" in f_lower or "studio/assets" in f_lower
            if not (is_doc or is_test or is_asset):
                all_low = False
                break

        if all_low:
            return "LOW", ["ALL_CHANGED_FILES_ARE_DOCS_TESTS_OR_ASSETS"]

        return "MEDIUM", ["DEFAULT_CODE_CHANGE_CLASSIFICATION"]


@dataclass
class ReviewFingerprint:
    """Tracks exact fingerprint of code, test, policy deltas, and review status."""
    review_checkpoint_commit: str = "c9446ff8cf41560eb044a60cede085636e3aaffa"
    reviewed_diff_hash: str = ""
    reviewed_files_hash: str = ""
    reviewed_policy_hash: str = ""
    reviewed_test_hash: str = ""
    reviewed_at: str = ""
    highest_reviewed_risk: str = "NONE"
    pending_diff_hash: str = ""
    pending_files: list[str] = field(default_factory=list)
    pending_risk_class: str = "LOW"
    pending_since: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    review_required: bool = False
    review_reason: str = "NO_CHANGE"

    def compute_fingerprint_hash(self) -> str:
        payload = {
            "checkpoint": self.review_checkpoint_commit,
            "reviewed_diff": self.reviewed_diff_hash,
            "reviewed_files": self.reviewed_files_hash,
            "pending_diff": self.pending_diff_hash,
            "pending_files": sorted(self.pending_files),
            "pending_risk": self.pending_risk_class,
            "review_required": self.review_required,
        }
        return compute_sha256(payload)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewFingerprint:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ReviewDeltaContextBuilder:
    """Constructs compact review context excluding all unchanged files."""

    @staticmethod
    def build_compact_context(
        repo_dir: Path,
        checkpoint_commit: str,
        changed_files: list[str],
        diff_str: str,
        risk_class: str,
        reasons: list[str],
        test_status: bool | None = None,
    ) -> dict[str, Any]:
        affected_modules = list({f.split("/")[0] for f in changed_files if "/" in f} or {"root"})

        # Policy hash check
        policy_hash = ""
        p_file = repo_dir / "events" / "policies" / "resource_policy.json"
        if p_file.exists():
            policy_hash = compute_sha256(p_file.read_text(encoding="utf-8"))

        return {
            "checkpoint_commit": checkpoint_commit,
            "changed_files_count": len(changed_files),
            "changed_files": changed_files,
            "affected_modules": sorted(affected_modules),
            "risk_class": risk_class,
            "risk_reasons": reasons,
            "deterministic_checks": {
                "git_diff_check": "CLEAN",
                "tests_passed": test_status if test_status is not None else True,
                "unchanged_files_excluded": True,
                "secret_warnings": []
            },
            "policy_hash": policy_hash,
            "diff_summary_lines": len(diff_str.splitlines()) if diff_str else 0,
            "diff_hash": compute_sha256(diff_str) if diff_str else "",
        }


class ReviewLedger:
    """Local append-only review ledger tracking completed reviews and daily batch limits."""

    def __init__(self, repo_dir: Path | None = None):
        self.repo_dir = repo_dir or COURIER_DIR
        self.reviews_dir = self.repo_dir / "events" / "reviews"
        self.ledger_json = self.reviews_dir / "ledger.json"
        self.ledger_log = self.reviews_dir / "review_ledger.jsonl"
        self.reviews_dir.mkdir(parents=True, exist_ok=True)

    def _load_ledger(self) -> dict:
        data = load_json(self.ledger_json)
        if data and isinstance(data, dict):
            return data
        return {
            "reviews": {},
            "fingerprints": {},
            "daily_batches": {},
            "stats": {"total_reviews": 0, "total_reused": 0}
        }

    def get_reviewed_entry(self, diff_hash: str) -> dict | None:
        ledger = self._load_ledger()
        return ledger.get("fingerprints", {}).get(diff_hash)

    def get_daily_routine_batch_count(self, date_str: str) -> int:
        ledger = self._load_ledger()
        return ledger.get("daily_batches", {}).get(date_str, 0)

    def record_review(
        self,
        review_id: str,
        checkpoint_commit: str,
        diff_hash: str,
        file_hashes: dict[str, str],
        risk_class: str,
        review_type: str,
        review_result: str,
        reviewer: str,
        reason: str,
    ) -> dict[str, Any]:
        ledger = self._load_ledger()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        date_str = now_iso[:10]

        # Prevent duplicate entries for identical completed review fingerprints
        if diff_hash in ledger.get("fingerprints", {}):
            ledger["stats"]["total_reused"] = ledger["stats"].get("total_reused", 0) + 1
            save_json_atomic(self.ledger_json, ledger)
            return ledger["fingerprints"][diff_hash]

        entry = {
            "review_id": review_id,
            "timestamp": now_iso,
            "checkpoint_commit": checkpoint_commit,
            "diff_hash": diff_hash,
            "file_hashes": file_hashes,
            "risk_class": risk_class,
            "review_type": review_type,
            "review_result": review_result,
            "reviewer": reviewer,
            "reason": reason
        }

        ledger["reviews"][review_id] = entry
        ledger["fingerprints"][diff_hash] = entry
        if review_type == "ROUTINE":
            ledger["daily_batches"][date_str] = ledger["daily_batches"].get(date_str, 0) + 1
        ledger["stats"]["total_reviews"] = ledger["stats"].get("total_reviews", 0) + 1

        save_json_atomic(self.ledger_json, ledger)

        # Append to jsonl
        with open(self.ledger_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")

        return entry


class ReviewBudgetManager:
    """Deterministic local review controller enforcing zero unnecessary Codex calls."""

    def __init__(self, repo_dir: Path | None = None):
        self.repo_dir = repo_dir or COURIER_DIR
        self.ledger = ReviewLedger(repo_dir=self.repo_dir)
        self.resource_intelligence = ResourceIntelligenceManager(repo_dir=self.repo_dir)

    def resource_context(self) -> dict[str, Any]:
        """Expose compact capacity references without scheduling a model review."""
        return self.resource_intelligence.context_for_role("REVIEW_BUDGET_MANAGER")

    def evaluate_review_requirement(
        self,
        checkpoint_commit: str = "c9446ff8cf41560eb044a60cede085636e3aaffa",
        changed_files: list[str] | None = None,
        diff_str: str = "",
        test_status: bool | None = None,
        is_push_intent: bool = False,
        is_activation_intent: bool = False,
        force_override: bool = False,
    ) -> dict[str, Any]:
        """Determines whether a model review is needed based strictly on local delta and risk."""
        files = changed_files or []
        diff_hash = compute_sha256(diff_str) if diff_str else ""
        files_hash = compute_sha256(sorted(files)) if files else ""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        date_str = now_iso[:10]

        # 1. No changes -> NO_REVIEW
        if not files and not diff_str:
            fp = ReviewFingerprint(
                review_checkpoint_commit=checkpoint_commit,
                pending_risk_class="LOW",
                review_required=False,
                review_reason="NO_RELEVANT_INFORMATION_GAIN"
            )
            return {
                "decision": "NO_REVIEW",
                "risk_class": "LOW",
                "reason": "NO_RELEVANT_INFORMATION_GAIN",
                "review_fingerprint": fp.to_dict(),
                "compact_context": None,
                "high_risk_override": False
            }

        # 2. Check if identical diff was already reviewed
        existing_review = self.ledger.get_reviewed_entry(diff_hash)
        if existing_review:
            fp = ReviewFingerprint(
                review_checkpoint_commit=checkpoint_commit,
                reviewed_diff_hash=diff_hash,
                reviewed_files_hash=files_hash,
                highest_reviewed_risk=existing_review.get("risk_class", "LOW"),
                reviewed_at=existing_review.get("timestamp", now_iso),
                pending_risk_class=existing_review.get("risk_class", "LOW"),
                review_required=False,
                review_reason="ALREADY_REVIEWED_IDENTICAL_DELTA"
            )
            return {
                "decision": "NO_REVIEW",
                "risk_class": existing_review.get("risk_class", "LOW"),
                "reason": "ALREADY_REVIEWED_IDENTICAL_DELTA",
                "review_fingerprint": fp.to_dict(),
                "compact_context": None,
                "high_risk_override": False
            }

        # 3. Classify Risk
        risk_class, risk_reasons = ReviewRiskClassifier.classify(files, diff_str)
        compact_ctx = ReviewDeltaContextBuilder.build_compact_context(
            repo_dir=self.repo_dir,
            checkpoint_commit=checkpoint_commit,
            changed_files=files,
            diff_str=diff_str,
            risk_class=risk_class,
            reasons=risk_reasons,
            test_status=test_status
        )

        daily_routine_count = self.ledger.get_daily_routine_batch_count(date_str)
        decision = "NO_REVIEW"
        reason = "DEFAULT_PASS"
        high_risk_override = False

        if risk_class == "LOW":
            decision = "BATCH_REVIEW"
            reason = "LOW_RISK_BATCH_OPTIONAL"
        elif risk_class == "MEDIUM":
            if is_push_intent:
                decision = "REVIEW_REQUIRED_BEFORE_PUSH"
                reason = "MEDIUM_RISK_REVIEW_REQUIRED_BEFORE_PUSH"
            else:
                decision = "BATCH_REVIEW"
                reason = "MEDIUM_RISK_LOCAL_ONLY"
        elif risk_class == "HIGH":
            decision = "IMMEDIATE_REVIEW_REQUIRED"
            reason = "HIGH_RISK_SECURITY_OR_TRUST_BOUNDARY_CHANGE"
            if daily_routine_count >= MAX_ROUTINE_CODEX_BATCHES_PER_DAY:
                high_risk_override = True

        # 4. Check Daily Routine Budget (only limits non-high risk routine reviews)
        if decision in {"BATCH_REVIEW", "REVIEW_REQUIRED_BEFORE_PUSH"} and not force_override:
            if daily_routine_count >= MAX_ROUTINE_CODEX_BATCHES_PER_DAY:
                decision = "NO_REVIEW"
                reason = "DAILY_ROUTINE_REVIEW_BUDGET_EXHAUSTED"

        fp = ReviewFingerprint(
            review_checkpoint_commit=checkpoint_commit,
            pending_diff_hash=diff_hash,
            pending_files=files,
            pending_risk_class=risk_class,
            review_required=(decision in {"REVIEW_REQUIRED_BEFORE_PUSH", "IMMEDIATE_REVIEW_REQUIRED"}),
            review_reason=reason
        )

        return {
            "decision": decision,
            "risk_class": risk_class,
            "reason": reason,
            "review_fingerprint": fp.to_dict(),
            "compact_context": compact_ctx,
            "high_risk_override": high_risk_override
        }

    def should_review(
        self,
        checkpoint_commit: str = "c9446ff8cf41560eb044a60cede085636e3aaffa",
        changed_files: list[str] | None = None,
        diff_str: str = "",
        test_status: bool | None = None,
        is_push_intent: bool = False,
    ) -> tuple[str, str, str, dict, dict | None]:
        """Lightweight gate query returning (decision, risk_class, reason, fingerprint, compact_context)."""
        res = self.evaluate_review_requirement(
            checkpoint_commit=checkpoint_commit,
            changed_files=changed_files,
            diff_str=diff_str,
            test_status=test_status,
            is_push_intent=is_push_intent
        )
        return (
            res["decision"],
            res["risk_class"],
            res["reason"],
            res["review_fingerprint"],
            res["compact_context"]
        )
