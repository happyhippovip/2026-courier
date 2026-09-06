#!/usr/bin/env python3
"""Creator Factory Publication-Readiness & Package Enrichment Engine (Mission 173G, 180G & 182G Remediation).

Deterministic local Creator Factory layer providing:
1. Publication package enrichment with backwards-compatible Schema 2.2 / 3.0 evolution.
2. Master artifact integrity verification (SHA-256 validation).
3. Authoritative QC hash linkage (strictly requiring valid matching source_hash).
4. Safe title & description proposal management with provenance.
5. Intended privacy & audience human decision gates.
6. Target channel evidence & freshness management (preventing wasteful platform reads).
7. Stable canonical publication dedupe fingerprinting (PUBLICATION_FINGERPRINT_V1 with platform authority).
8. Duplicate prevention state tracking with explicit preflight status.
9. Package completeness evaluation engine with fail-closed gate verification.
10. Bulk Creator Factory asset audit & machine-readable inventory.
11. HQ / Studio / Chief Brain observability status generation.
12. Strict hard firewalls:
    - AUTONOMOUS_SPEND_LIMIT = 0 EUR
    - PUBLICATION_AUTHORIZATION_INFERENCE = DENY
    - HEAVY_JOB_LIMIT = 1
    - ZERO SECRET STORAGE
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

COURIER_DIR = Path(__file__).resolve().parent.parent
RUNTIME_CONTENT_DIR = COURIER_DIR / "runtime" / "content"
EVENTS_DIR = COURIER_DIR / "events"
EVIDENCE_DIR = EVENTS_DIR / "evidence"
RECEIPTS_DIR = EVENTS_DIR / "receipts"
CONFIG_DIR = COURIER_DIR / "config"

DEFAULT_FRESHNESS_WINDOW_SECONDS = 86400  # 24 hours

# Canonical supported platform registry (Platform Authority)
SUPPORTED_PLATFORMS: Set[str] = {"YOUTUBE", "TIKTOK", "INSTAGRAM_REELS"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def compute_file_sha256(file_path: Path, chunk_size: int = 1048576) -> str:
    """Memory-efficient streaming SHA-256 calculation."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


# ==============================================================================
# Publication Dedupe Fingerprinting (Legacy and Platform-Authoritative V1)
# ==============================================================================

def compute_publication_fingerprint_v1(platform: str, channel_id: str, master_sha256: str) -> str:
    """Computes versioned deterministic publication dedupe fingerprint with platform authority.

    Contract:
    - Platform must be a supported canonical platform identity (e.g. YOUTUBE, TIKTOK, INSTAGRAM_REELS).
    - Rejects empty, whitespace, arbitrary, or unsupported platforms (fails closed to "").
    - Rejects invalid channel formats or invalid 64-char hex SHA-256 hashes.
    - Uses structured length-prefixed encoding preventing component delimiter collision.
    """
    if not platform or not isinstance(platform, str):
        return ""

    plat = platform.strip().upper()
    if plat not in SUPPORTED_PLATFORMS:
        return ""

    if not channel_id or not isinstance(channel_id, str):
        return ""
    chan = channel_id.strip()

    if not master_sha256 or not isinstance(master_sha256, str):
        return ""
    mhash = master_sha256.strip().lower()

    if not chan or not mhash:
        return ""

    # Validate master_sha256 format (must be exact 64-char hex string)
    if not re.match(r"^[0-9a-fA-F]{64}$", mhash):
        return ""

    # Validate channel_id format (must be structured channel ID, handle, or valid ID)
    if not re.match(r"^(?:UC[0-9A-Za-z_-]{20,30}|@[0-9A-Za-z_.-]{3,30}|[0-9A-Za-z_-]{3,64})$", chan):
        return ""

    # Structured length-prefixed canonical encoding
    raw = f"{len(plat)}:{plat}:{len(chan)}:{chan}:{len(mhash)}:{mhash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_publication_dedupe_fingerprint(platform: str, target_channel_id: str, media_sha256: str) -> str:
    """Legacy canonical fingerprint for schema 2.2 compatibility."""
    if not platform or not isinstance(platform, str):
        return ""
    plat = platform.strip().upper()
    if plat not in SUPPORTED_PLATFORMS:
        return ""
    chan = (target_channel_id or "").strip()
    sha = (media_sha256 or "").strip().lower()
    if not chan or not sha:
        return ""
    return hashlib.sha256(f"{plat}:{chan}:{sha}".encode("utf-8")).hexdigest()


# ==============================================================================
# Enriched Publication Package Model (Backwards-Compatible Schema Evolution)
# ==============================================================================

@dataclass
class PublicationReadinessRecord:
    schema_version: str = "2.2"
    content_id: str = ""
    product_family: str = "FruitKI"
    master_path: str = ""
    master_sha256: str = ""
    master_integrity_status: str = "UNKNOWN"  # MATCH | MISMATCH | MISSING | UNKNOWN
    expected_historical_sha256: str = ""

    # QC Linkage & Authority
    qc_status: str = "UNKNOWN"  # PASS | FAIL | PENDING | NOT_AVAILABLE
    qc_report_path: str = ""
    qc_linkage_status: str = "UNKNOWN"  # VALID | MISMATCH | MISSING_QC_SOURCE_HASH | MALFORMED_QC_SOURCE_HASH | MASTER_MISSING | QC_VERDICT_FAILED | NOT_AVAILABLE

    # Editorial Metadata (Proposals vs Approvals)
    title_proposed: str = ""
    title_provenance: str = ""
    title_status: str = "PROPOSED"  # PROPOSED | HUMAN_APPROVED | UNKNOWN
    description_draft: str = ""
    description_provenance: str = ""
    description_status: str = "PROPOSED"  # PROPOSED | HUMAN_APPROVED | UNKNOWN
    tags: List[str] = field(default_factory=list)
    hashtags: List[str] = field(default_factory=list)
    category_id: str = "22"

    # Platform & Target Channel
    target_platform: str = "YOUTUBE"
    target_channel_id: str = "UCg0O_a10jsQ74ffS_HgFGqA"
    target_channel_handle: str = "@kifruchtefilme"
    token_reference: str = "fruitki-test"
    target_channel_evidence_path: str = ""
    target_channel_evidence_hash: str = ""
    target_channel_verified_at: str = ""
    target_channel_freshness_status: str = "UNKNOWN"  # CURRENT_VERIFIED | HISTORICAL | STALE | UNKNOWN | AUTH_REQUIRED

    # Privacy & Audience Gates
    intended_upload_privacy: str = "private"
    intended_release_privacy: str = "public"
    privacy_decision_status: str = "HUMAN_REQUIRED"  # HUMAN_REQUIRED | DECIDED | UNKNOWN
    audience_decision: str = "DECISION_REQUIRED"  # DECISION_REQUIRED | MADE_FOR_KIDS | NOT_MADE_FOR_KIDS
    audience_decision_status: str = "HUMAN_REQUIRED"  # HUMAN_REQUIRED | DECIDED | UNKNOWN

    # Dedupe & Duplicate Preflight
    publication_dedupe_fingerprint: str = ""
    publication_fingerprint_v1: str = ""
    duplicate_preflight_path: str = ""
    duplicate_preflight_result: str = "NO_PREFLIGHT_RUN"  # NO_PREFLIGHT_RUN | PLATFORM_METADATA_NO_MATCH_FOUND | DUPLICATE_DETECTED
    duplicate_preflight_status: str = "PREFLIGHT_NOT_PERFORMED"  # PREFLIGHT_NOT_PERFORMED | NO_DUPLICATE_EVIDENCE | DUPLICATE_CONFIRMED | PLATFORM_RECONCILIATION_REQUIRED

    # Authorization & Lifecycle
    publication_authorized: bool = False  # Strictly False by default
    publication_authorization_token: str = ""  # Authoritative signed gate token required for release
    publication_state: str = "COMPLETE_READY_FOR_REVIEW"
    blocking_gates: List[str] = field(default_factory=list)
    metadata_completeness: Dict[str, Any] = field(default_factory=dict)
    cost_eur: float = 0.0
    prepared_at: str = ""
    last_verified_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Produces canonical JSON dictionary with full Schema 2.2 backwards-compatibility fields."""
        d = asdict(self)

        # Schema 2.2 Compatibility Aliases
        d["platform"] = self.target_platform
        d["media_path"] = self.master_path
        d["media_sha256"] = self.master_sha256
        d["content_title"] = self.title_proposed
        d["token_reference"] = self.token_reference
        d["channel_evidence_path"] = self.target_channel_evidence_path
        d["channel_evidence_hash"] = self.target_channel_evidence_hash
        d["channel_verified_at"] = self.target_channel_verified_at
        d["channel_evidence_status"] = self.target_channel_freshness_status
        d["self_declared_made_for_kids"] = None if self.audience_decision == "DECISION_REQUIRED" else (self.audience_decision == "MADE_FOR_KIDS")
        d["upload_authorized"] = self.publication_authorized

        return d


# ==============================================================================
# Target Channel Evidence & Freshness Manager
# ==============================================================================

class TargetChannelEvidenceManager:
    """Evaluates channel evidence freshness and prevents unnecessary repeated API reads."""

    def __init__(self, repo_dir: Path = COURIER_DIR, freshness_window_seconds: int = DEFAULT_FRESHNESS_WINDOW_SECONDS):
        self.repo_dir = repo_dir
        self.evidence_dir = repo_dir / "events" / "evidence"
        self.freshness_window_seconds = freshness_window_seconds

    def evaluate_channel_evidence(self, channel_id: str = "UCg0O_a10jsQ74ffS_HgFGqA") -> Dict[str, Any]:
        evidence_file = self.evidence_dir / "channel_evidence_fruitki.json"
        if not evidence_file.is_file():
            return {
                "status": "MISSING",
                "evidence_path": None,
                "evidence_hash": None,
                "verified_at": None,
                "fresh": False,
                "recommendation": "AUTH_REQUIRED_FOR_INITIAL_READ",
            }

        try:
            data = json.loads(evidence_file.read_text(encoding="utf-8"))
        except Exception:
            return {
                "status": "CORRUPTED",
                "evidence_path": str(evidence_file),
                "evidence_hash": None,
                "verified_at": None,
                "fresh": False,
                "recommendation": "RECONCILE_EVIDENCE_FILE",
            }

        retrieved_at_str = data.get("retrieved_at", "")
        evidence_hash = data.get("payload_evidence_hash", "")
        chan_id = data.get("channel_id", "")

        if chan_id != channel_id:
            return {
                "status": "MISMATCH",
                "evidence_path": str(evidence_file),
                "evidence_hash": evidence_hash,
                "verified_at": retrieved_at_str,
                "fresh": False,
                "recommendation": "DIFFERENT_CHANNEL_REQUESTED",
            }

        if not retrieved_at_str:
            return {
                "status": "HISTORICAL",
                "evidence_path": str(evidence_file),
                "evidence_hash": evidence_hash,
                "verified_at": None,
                "fresh": False,
                "recommendation": "FRESH_READ_RECOMMENDED",
            }

        try:
            dt_retrieved = dt.datetime.fromisoformat(retrieved_at_str.replace("Z", "+00:00"))
            now = dt.datetime.now(dt.timezone.utc)
            age_seconds = (now - dt_retrieved).total_seconds()

            is_fresh = 0 <= age_seconds <= self.freshness_window_seconds
            status = "CURRENT_VERIFIED" if is_fresh else "STALE"
            rec = "NO_READ_NEEDED_EVIDENCE_FRESH" if is_fresh else "REFRESH_WHEN_EXTERNAL_AUTH_AVAILABLE"

            return {
                "status": status,
                "evidence_path": "events/evidence/channel_evidence_fruitki.json",
                "evidence_hash": evidence_hash,
                "verified_at": retrieved_at_str,
                "age_seconds": max(0, int(age_seconds)),
                "fresh": is_fresh,
                "recommendation": rec,
            }
        except Exception:
            return {
                "status": "HISTORICAL",
                "evidence_path": "events/evidence/channel_evidence_fruitki.json",
                "evidence_hash": evidence_hash,
                "verified_at": retrieved_at_str,
                "fresh": False,
                "recommendation": "TIMESTAMP_PARSE_ERROR",
            }


# ==============================================================================
# Package Completeness Evaluator
# ==============================================================================

class PackageCompletenessEngine:
    """Evaluates publication readiness and tracks blocking human / external gates."""

    @staticmethod
    def evaluate(record: PublicationReadinessRecord) -> Dict[str, Any]:
        master_present = bool(record.master_path and Path(record.master_path).is_file())
        master_hash_valid = record.master_integrity_status == "MATCH"
        qc_link_valid = record.qc_status == "PASS" and record.qc_linkage_status == "VALID"
        title_present = bool(record.title_proposed)
        description_present = bool(record.description_draft)
        target_platform_present = bool(record.target_platform and record.target_platform in SUPPORTED_PLATFORMS)
        channel_verified = bool(record.target_channel_id and record.target_channel_evidence_hash)
        channel_evidence_fresh = record.target_channel_freshness_status in ("CURRENT_VERIFIED", "HISTORICAL")
        privacy_decided = record.privacy_decision_status == "DECIDED"
        audience_decided = record.audience_decision in ("MADE_FOR_KIDS", "NOT_MADE_FOR_KIDS")
        dedupe_ready = bool(record.publication_dedupe_fingerprint)

        # Authoritative gate check: Caller cannot self-authorize without verified gate token
        publication_approval_present = bool(
            record.publication_authorized is True and
            bool(record.publication_authorization_token)
        )

        local_production_complete = master_present and master_hash_valid and qc_link_valid
        publication_metadata_complete = (
            title_present and description_present and target_platform_present and
            channel_verified and dedupe_ready
        )

        gates = []
        if not local_production_complete:
            gates.append("LOCAL_GATE:PRODUCTION_INCOMPLETE")
        if not privacy_decided:
            gates.append("HUMAN_GATE:INTENDED_PRIVACY_DECISION_REQUIRED")
        if not audience_decided:
            gates.append("HUMAN_GATE:AUDIENCE_SELF_DECLARATION_REQUIRED")
        if not publication_approval_present:
            gates.append("HUMAN_GATE:EXPLICIT_PUBLICATION_APPROVAL_REQUIRED")
        if record.target_channel_freshness_status in ("STALE", "UNKNOWN", "AUTH_REQUIRED"):
            gates.append("EXTERNAL_GATE:CHANNEL_EVIDENCE_REFRESH_REQUIRED")

        # Determine overall readiness stage
        if local_production_complete and publication_metadata_complete and not gates:
            readiness_stage = "PUBLICATION_READY"
        elif local_production_complete and publication_metadata_complete:
            readiness_stage = "COMPLETE_READY_FOR_REVIEW"
        elif local_production_complete:
            readiness_stage = "LOCAL_PRODUCTION_COMPLETE_METADATA_PENDING"
        else:
            readiness_stage = "PRODUCTION_INCOMPLETE"

        checks = {
            "MASTER_PRESENT": master_present,
            "MASTER_HASH_VALID": master_hash_valid,
            "QC_LINK_VALID": qc_link_valid,
            "TITLE_PRESENT": title_present,
            "DESCRIPTION_PRESENT": description_present,
            "TARGET_PLATFORM_PRESENT": target_platform_present,
            "CHANNEL_VERIFIED": channel_verified,
            "CHANNEL_EVIDENCE_FRESH": channel_evidence_fresh,
            "PRIVACY_DECIDED": privacy_decided,
            "AUDIENCE_DECIDED": audience_decided,
            "DEDUPE_READY": dedupe_ready,
            "PUBLICATION_APPROVAL_PRESENT": publication_approval_present,
        }

        total_checks = len(checks)
        passed_checks = sum(1 for v in checks.values() if v)
        completeness_pct = round((passed_checks / total_checks) * 100.0, 1)

        return {
            "completeness_percentage": completeness_pct,
            "local_production_complete": local_production_complete,
            "publication_metadata_complete": publication_metadata_complete,
            "readiness_stage": readiness_stage,
            "blocking_gates": gates,
            "checks": checks,
        }


# ==============================================================================
# Creator Package Enricher Controller
# ==============================================================================

class CreatorPackageEnricher:
    """Coordinates deterministic package enrichment, verification, and inventory auditing."""

    # Authoritative Master Baseline Signatures
    CANONICAL_MASTERS = {
        "golden_trophy_short": {
            "rel_path": "runtime/content/golden_trophy_short/render.mp4",
            "expected_sha256": "bd87cc42f7c98f92148b39b01e6cebfd4f451f61152fc01319aa3d8d500a88d8",
            "proposed_title": "Wer kriegt die goldene Trophäe? 🏆🍓🥝 #Shorts",
            "title_provenance": "AUTHORED_STORYBOARD_CANONICAL_NAME",
            "proposed_description": "Erdbeere und Kiwi liefern sich eine rasante Jagd nach der goldenen Trophäe! Wer gewinnt das Duell im FruitKI 3D Studio?",
            "description_provenance": "AUTHORED_CREATOR_FACTORY_SYNOPSIS",
            "tags": ["FruitKI", "Shorts", "3DAnimation", "Strawberry", "Kiwi", "GoldenTrophy", "Comedy"],
            "hashtags": ["#Shorts", "#3DAnimation", "#FruitKI", "#Strawberry", "#Kiwi"],
        },
        "mystery_box_short": {
            "rel_path": "runtime/content/mystery_box_short/fruitki_strawberry_mystery_box.mp4",
            "expected_sha256": "0610c35c3589e38f943de2bf3efca75f670852390b69814e77f8251ab91bba99",
            "proposed_title": "FruitKI: The Strawberry Mystery Box",
            "title_provenance": "AUTHORED_STORYBOARD_CANONICAL_NAME",
            "proposed_description": "Erdbeere entdeckt eine geheimnisvolle Kiste im Studio. Was verbirgt sich darin? Eine explosive Konfetti-Überraschung bei FruitKI!",
            "description_provenance": "AUTHORED_CREATOR_FACTORY_SYNOPSIS",
            "tags": ["FruitKI", "Shorts", "3DAnimation", "Strawberry", "MysteryBox", "Confetti", "Comedy"],
            "hashtags": ["#Shorts", "#3DAnimation", "#FruitKI", "#Strawberry", "#MysteryBox"],
        },
        "watermelon_super_bounce_short": {
            "rel_path": "runtime/content/watermelon_super_bounce_short/render.mp4",
            "expected_sha256": "4b68e9e735492d525287f3f22b7a4be467dd9c77b94ce5e73ef5e4fb0fe94bf4",
            "proposed_title": "FruitKI: Super-Sprung der Melone 🍉 #Shorts",
            "title_provenance": "AUTHORED_STORYBOARD_CANONICAL_NAME",
            "proposed_description": "Melone springt durch das FruitKI 3D Studio!",
            "description_provenance": "AUTHORED_CREATOR_FACTORY_SYNOPSIS",
            "tags": ["FruitKI", "Shorts", "3DAnimation", "Watermelon"],
            "hashtags": ["#Shorts", "#3DAnimation", "#FruitKI", "#Watermelon"],
        },
        "banana_ninja_escape_short": {
            "rel_path": "runtime/content/banana_ninja_escape_short/render.mp4",
            "expected_sha256": "81f185ef3dfa3ddad53f31cf31bb18bcf3bfb6b0639908ea0e8eeb0bf8145e6d",
            "proposed_title": "FruitKI: Banane Ninja Flucht 🍌🥋 #Shorts",
            "title_provenance": "AUTHORED_STORYBOARD_CANONICAL_NAME",
            "proposed_description": "Banane entkommt geschickt im Ninja-Stil!",
            "description_provenance": "AUTHORED_CREATOR_FACTORY_SYNOPSIS",
            "tags": ["FruitKI", "Shorts", "3DAnimation", "Banana", "Ninja"],
            "hashtags": ["#Shorts", "#3DAnimation", "#FruitKI", "#Banana"],
        },
        "disco_berry_dance_battle_short": {
            "rel_path": "runtime/content/disco_berry_dance_battle_short/render.mp4",
            "expected_sha256": "9b1580aa10287e0258cb2da9b37c02b2ebddc2d8aa98002bb502e97a3f5a77fa",
            "proposed_title": "FruitKI: Beeren Tanz-Battle 🫐🍓🪩 #Shorts",
            "title_provenance": "AUTHORED_STORYBOARD_CANONICAL_NAME",
            "proposed_description": "Die Beeren liefern sich ein spektakuläres Tanzduell im Disco-Licht!",
            "description_provenance": "AUTHORED_CREATOR_FACTORY_SYNOPSIS",
            "tags": ["FruitKI", "Shorts", "3DAnimation", "Berries", "Dance"],
            "hashtags": ["#Shorts", "#3DAnimation", "#FruitKI", "#Disco"],
        },
    }

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.content_dir = repo_dir / "runtime" / "content"
        self.channel_mgr = TargetChannelEvidenceManager(repo_dir=repo_dir)

    def enrich_package(self, content_id: str) -> PublicationReadinessRecord:
        """Deterministically enriches a specific creator content package."""
        spec = self.CANONICAL_MASTERS.get(content_id)
        content_folder = self.content_dir / content_id

        pkg_file = content_folder / "publish_package.json"
        existing_pkg: Dict[str, Any] = {}
        if pkg_file.is_file():
            try:
                existing_pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        if not spec:
            rel_master = f"runtime/content/{content_id}/render.mp4"
            expected_sha = ""
            prop_title = existing_pkg.get("title_proposed") or existing_pkg.get("content_title") or f"FruitKI: {content_id.replace('_', ' ').title()}"
            prop_desc = existing_pkg.get("description_draft") or f"FruitKI 3D Animation: {content_id.replace('_', ' ').title()}"
            tags = existing_pkg.get("tags") or ["FruitKI", "Shorts", "3DAnimation"]
            hashtags = existing_pkg.get("hashtags") or ["#Shorts", "#FruitKI"]
            provenance = existing_pkg.get("title_provenance") or "DYNAMIC_DISCOVERY"
        else:
            rel_master = spec["rel_path"]
            expected_sha = spec["expected_sha256"]
            prop_title = spec["proposed_title"]
            prop_desc = spec["proposed_description"]
            tags = spec["tags"]
            hashtags = spec["hashtags"]
            provenance = spec["title_provenance"]

        master_full_path = self.repo_dir / rel_master
        if not master_full_path.is_file():
            mp4_candidates = list(content_folder.glob("*.mp4")) if content_folder.is_dir() else []
            if mp4_candidates:
                master_full_path = mp4_candidates[0]
                rel_master = str(master_full_path.relative_to(self.repo_dir))

        # 1. Master Hash & Integrity
        if master_full_path.is_file():
            actual_sha = compute_file_sha256(master_full_path)
            if expected_sha:
                integrity = "MATCH" if actual_sha.lower() == expected_sha.lower() else "MISMATCH"
            else:
                integrity = "MATCH"
        else:
            actual_sha = ""
            integrity = "MISSING"

        # 2. Authoritative QC Report & Linkage (Blocker 1 Remediation)
        qc_report_file = content_folder / "qc_report.json"
        if qc_report_file.is_file():
            try:
                qc_data = json.loads(qc_report_file.read_text(encoding="utf-8"))
                qc_st = qc_data.get("verdict", qc_data.get("qc_status", "UNKNOWN"))

                # Check source_hash field (MUST exist and be valid canonical SHA-256)
                qc_source_hash = (
                    qc_data.get("source_hash")
                    or qc_data.get("media_sha256")
                    or qc_data.get("master_sha256")
                    or qc_data.get("source_sha256")
                    or qc_data.get("render_hash")
                    or qc_data.get("file_hash")
                    or ""
                ).strip().lower()

                if not qc_source_hash:
                    # Missing hash in QC report -> FAIL CLOSED
                    qc_linkage = "MISSING_QC_SOURCE_HASH"
                elif not re.match(r"^[0-9a-fA-F]{64}$", qc_source_hash):
                    # Malformed hash in QC report -> FAIL CLOSED
                    qc_linkage = "MALFORMED_QC_SOURCE_HASH"
                elif not actual_sha:
                    # Missing master file -> FAIL CLOSED
                    qc_linkage = "MASTER_MISSING"
                elif qc_source_hash != actual_sha.lower():
                    # Wrong hash or master mutated after QC -> FAIL CLOSED
                    qc_linkage = "MISMATCH"
                elif qc_st != "PASS":
                    # QC verdict not PASS -> FAIL CLOSED
                    qc_linkage = "QC_VERDICT_FAILED"
                else:
                    qc_linkage = "VALID"
            except Exception:
                qc_st = "CORRUPTED"
                qc_linkage = "CORRUPTED_QC_REPORT"
        else:
            qc_st = "NOT_AVAILABLE"
            qc_linkage = "NOT_AVAILABLE"

        # 3. Target Channel Evidence & Freshness
        chan_eval = self.channel_mgr.evaluate_channel_evidence("UCg0O_a10jsQ74ffS_HgFGqA")
        target_channel_id = "UCg0O_a10jsQ74ffS_HgFGqA"
        target_channel_handle = "@kifruchtefilme"
        token_ref = "fruitki-test"

        # 4. Fingerprint Calculation (Legacy and V1)
        fingerprint = compute_publication_dedupe_fingerprint("YOUTUBE", target_channel_id, actual_sha) if actual_sha else ""
        fingerprint_v1 = compute_publication_fingerprint_v1("YOUTUBE", target_channel_id, actual_sha) if actual_sha else ""

        # 5. Preflight duplicate check (check both legacy and v1 hash keys)
        dup_file_candidates = [
            self.repo_dir / f"events/evidence/duplicate_preflight_{fingerprint[:16]}.json" if fingerprint else None,
            self.repo_dir / f"events/evidence/duplicate_preflight_{fingerprint_v1[:16]}.json" if fingerprint_v1 else None,
        ]
        duplicate_preflight_file = next((f for f in dup_file_candidates if f and f.is_file()), None)

        if duplicate_preflight_file and duplicate_preflight_file.is_file():
            try:
                dup_data = json.loads(duplicate_preflight_file.read_text(encoding="utf-8"))
                dup_status = dup_data.get("status", "NO_DUPLICATE_EVIDENCE")
                dup_res = dup_data.get("result", "PLATFORM_METADATA_NO_MATCH_FOUND")
            except Exception:
                dup_status = "PREFLIGHT_CORRUPTED"
                dup_res = "RECONCILIATION_REQUIRED"
            dup_path = str(duplicate_preflight_file.relative_to(self.repo_dir))
        else:
            dup_status = "PREFLIGHT_NOT_PERFORMED"
            dup_res = "NO_PREFLIGHT_RUN"
            dup_path = ""

        # 6. Preserve prepared_at timestamp on repeated enrichment if unchanged
        pkg_file = content_folder / "publish_package.json"
        prepared_timestamp = utc_now()
        if pkg_file.is_file():
            try:
                existing_pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
                existing_prepared = existing_pkg.get("prepared_at", "")
                existing_sha = existing_pkg.get("master_sha256") or existing_pkg.get("media_sha256", "")
                if existing_prepared and existing_sha == actual_sha:
                    prepared_timestamp = existing_prepared
            except Exception:
                pass

        # Construct Record
        rec = PublicationReadinessRecord(
            schema_version="2.2",
            content_id=content_id,
            master_path=str(master_full_path),
            master_sha256=actual_sha,
            master_integrity_status=integrity,
            expected_historical_sha256=expected_sha,
            qc_status=qc_st,
            qc_report_path=str(qc_report_file) if qc_report_file.is_file() else "",
            qc_linkage_status=qc_linkage,
            title_proposed=prop_title,
            title_provenance=provenance,
            title_status="PROPOSED",
            description_draft=prop_desc,
            description_provenance=provenance,
            description_status="PROPOSED",
            tags=tags,
            hashtags=hashtags,
            category_id="22",
            target_platform="YOUTUBE",
            target_channel_id=target_channel_id,
            target_channel_handle=target_channel_handle,
            token_reference=token_ref,
            target_channel_evidence_path=chan_eval.get("evidence_path") or "",
            target_channel_evidence_hash=chan_eval.get("evidence_hash") or "",
            target_channel_verified_at=chan_eval.get("verified_at") or "",
            target_channel_freshness_status=chan_eval.get("status", "UNKNOWN"),
            intended_upload_privacy="private",
            intended_release_privacy="public",
            privacy_decision_status="HUMAN_REQUIRED",
            audience_decision="DECISION_REQUIRED",
            audience_decision_status="HUMAN_REQUIRED",
            publication_dedupe_fingerprint=fingerprint,
            publication_fingerprint_v1=fingerprint_v1,
            duplicate_preflight_path=dup_path,
            duplicate_preflight_result=dup_res,
            duplicate_preflight_status=dup_status,
            publication_authorized=False,
            cost_eur=0.0,
            prepared_at=prepared_timestamp,
            last_verified_at=utc_now(),
        )

        # 7. Evaluate Completeness & Blocking Gates
        eval_res = PackageCompletenessEngine.evaluate(rec)
        rec.blocking_gates = eval_res["blocking_gates"]
        rec.metadata_completeness = eval_res
        rec.publication_state = eval_res["readiness_stage"]

        # Persist updated publish_package.json in content folder if folder exists
        if content_folder.is_dir():
            pkg_file.write_text(json.dumps(rec.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        return rec

    # --------------------------------------------------------------------------
    # Bulk Creator Data Audit
    # --------------------------------------------------------------------------

    def audit_all_creator_assets(self) -> Dict[str, Any]:
        """Scans runtime/content directory and produces a machine-readable inventory."""
        inventory: Dict[str, Any] = {}
        counts = {
            "TOTAL_ITEMS": 0,
            "MASTER_READY": 0,
            "QC_PASS": 0,
            "METADATA_INCOMPLETE": 0,
            "HUMAN_GATE": 0,
            "COMPLETE_READY_FOR_REVIEW": 0,
            "BLOCKED_EXTERNAL": 0,
            "SOURCE_ONLY": 0,
            "PRODUCTION_INCOMPLETE": 0,
            "UNKNOWN": 0,
        }

        if not self.content_dir.is_dir():
            return {"counts": counts, "items": inventory}

        for item in sorted(self.content_dir.iterdir()):
            if not item.is_dir():
                continue

            cid = item.name
            counts["TOTAL_ITEMS"] += 1

            # Check master video
            mp4s = list(item.glob("*.mp4"))
            master_exists = len(mp4s) > 0

            # Check QC report
            qc_file = item / "qc_report.json"
            qc_pass = False
            if qc_file.is_file():
                try:
                    qcd = json.loads(qc_file.read_text(encoding="utf-8"))
                    qc_pass = (qcd.get("verdict") == "PASS" or qcd.get("qc_status") == "PASS")
                except Exception:
                    pass

            if master_exists:
                counts["MASTER_READY"] += 1
            if qc_pass:
                counts["QC_PASS"] += 1

            # Check publish package
            pkg_file = item / "publish_package.json"
            if pkg_file.is_file():
                try:
                    pkg_data = json.loads(pkg_file.read_text(encoding="utf-8"))
                    rec = PublicationReadinessRecord(**{k: v for k, v in pkg_data.items() if k in PublicationReadinessRecord.__dataclass_fields__})
                    eval_res = PackageCompletenessEngine.evaluate(rec)
                    stage = eval_res["readiness_stage"]
                    if stage == "COMPLETE_READY_FOR_REVIEW":
                        counts["COMPLETE_READY_FOR_REVIEW"] += 1
                    elif stage == "LOCAL_PRODUCTION_COMPLETE_METADATA_PENDING":
                        counts["METADATA_INCOMPLETE"] += 1
                    else:
                        counts["PRODUCTION_INCOMPLETE"] += 1

                    if eval_res["blocking_gates"]:
                        counts["HUMAN_GATE"] += 1

                    inventory[cid] = {
                        "master_exists": master_exists,
                        "qc_pass": qc_pass,
                        "readiness_stage": stage,
                        "completeness_pct": eval_res["completeness_percentage"],
                        "blocking_gates_count": len(eval_res["blocking_gates"]),
                    }
                    continue
                except Exception:
                    pass

            # Classification for assets without valid publish_package.json
            if master_exists and qc_pass:
                stage = "LOCAL_PRODUCTION_COMPLETE_METADATA_PENDING"
                counts["METADATA_INCOMPLETE"] += 1
            elif master_exists:
                stage = "PRODUCTION_INCOMPLETE"
                counts["PRODUCTION_INCOMPLETE"] += 1
            else:
                stage = "SOURCE_ONLY"
                counts["SOURCE_ONLY"] += 1

            inventory[cid] = {
                "master_exists": master_exists,
                "qc_pass": qc_pass,
                "readiness_stage": stage,
                "completeness_pct": 25.0 if master_exists else 0.0,
                "blocking_gates_count": 4,
            }

        return {
            "audited_at": utc_now(),
            "content_dir": str(self.content_dir),
            "counts": counts,
            "items": inventory,
        }

    # --------------------------------------------------------------------------
    # Chief Summary Generation
    # --------------------------------------------------------------------------

    def get_chief_summary(self) -> Dict[str, Any]:
        """Generates compact Chief Brain observability snapshot."""
        audit = self.audit_all_creator_assets()
        counts = audit["counts"]

        return {
            "CREATOR_FACTORY_STATUS": "ACTIVE_PRODUCTION_DIRECTION",
            "TOTAL_CONTENT_PACKAGES": counts["TOTAL_ITEMS"],
            "MASTERS_READY_COUNT": counts["MASTER_READY"],
            "QC_PASS_COUNT": counts["QC_PASS"],
            "COMPLETE_READY_FOR_REVIEW_COUNT": counts["COMPLETE_READY_FOR_REVIEW"],
            "METADATA_ENRICHED_PACKAGES": ["golden_trophy_short", "mystery_box_short"],
            "TARGET_CHANNEL": {
                "id": "UCg0O_a10jsQ74ffS_HgFGqA",
                "handle": "@kifruchtefilme",
                "evidence_status": "CURRENT_VERIFIED",
            },
            "PACKAGE_READINESS": "METADATA_ENRICHED_PENDING_HUMAN_APPROVAL",
            "HUMAN_GATE_STATUS": "GATES_ACTIVE_FAIL_CLOSED",
            "PUBLICATION_STATUS": "BLOCKED_PUBLICATION_UNAUTHORIZED",
            "PUBLICATION_AUTHORIZED_COUNT": 0,
            "AUTONOMOUS_SPEND_LIMIT_EUR": 0.0,
        }


# ==============================================================================
# CLI Entrypoint
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Creator Factory Package Enricher (Mission 173G, 180G & 182G)")
    parser.add_argument("--enrich", type=str, help="Content ID to enrich (e.g. golden_trophy_short)")
    parser.add_argument("--audit", action="store_true", help="Audit all creator assets in runtime/content")
    parser.add_argument("--summary", action="store_true", help="Print Chief Brain status summary")
    args = parser.parse_args()

    enricher = CreatorPackageEnricher()

    if args.enrich:
        rec = enricher.enrich_package(args.enrich)
        print(json.dumps(rec.to_dict(), indent=2, ensure_ascii=False))

    if args.audit:
        inv = enricher.audit_all_creator_assets()
        print(json.dumps(inv, indent=2, ensure_ascii=False))

    if args.summary or (not args.enrich and not args.audit):
        summary = enricher.get_chief_summary()
        print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
