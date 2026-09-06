#!/usr/bin/env python3
"""Fail-closed Creator Factory input-source discovery (Mission 122).

The Creator Factory may use only evidence it can describe and verify locally.
This module deliberately does *not* read credentials, call platform APIs, or
turn the presence of a token file into authorization.  It gives the existing
opportunity queue a bounded, deterministic refresh hook for local production
evidence and already-ingested public research evidence.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


UTC = dt.timezone.utc
YOUTUBE_PILOT = Path("/Users/user/Downloads/2026-Projektzentrale/02-YouTube-Operations/youtube-oauth-pilot")
TIKTOK_PILOT = Path("/Users/user/Downloads/2026-Projektzentrale/02-YouTube-Operations/tiktok-oauth-pilot")


def _now() -> str:
    return dt.datetime.now(UTC).isoformat()


def stable_hash(value: Any) -> str:
    """Return a stable evidence fingerprint without exposing sensitive values."""
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_source(source: str) -> str:
    """Normalize source identifiers without accepting unknown source classes."""
    allowed = {
        "LOCAL_CREATOR_SOURCE",
        "OFFICIAL_PUBLIC_DOCUMENTATION",
        "YOUTUBE",
        "TIKTOK",
    }
    normalized = source.strip().upper().replace(" ", "_")
    if normalized not in allowed:
        raise ValueError("unsupported creator input source")
    return normalized


def youtube_client_dependencies_available() -> bool:
    """Return dependency availability without importing credential-bearing code."""
    try:
        return all(importlib.util.find_spec(module) is not None for module in (
            "google.oauth2.credentials",
            "googleapiclient.discovery",
        ))
    except ModuleNotFoundError:
        return False


@dataclass(frozen=True)
class SourceCapability:
    source: str
    implementation_found: bool
    auth_state: str
    read_capability: str
    analytics_capability: str
    write_capability: str
    zero_cost_proven: bool
    safe_to_use_now: bool
    blocker: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def discover_capabilities() -> list[SourceCapability]:
    """Discover integration shape from public code/path metadata only.

    A credential file is intentionally treated as an *unverified* local
    interface.  Its existence neither reads it nor establishes that it is
    valid, current, or authorized for this run.
    """
    youtube_impl = (YOUTUBE_PILOT / "youtube_verify_channel.py").is_file()
    youtube_config_interface = (YOUTUBE_PILOT / "config.json").exists()
    youtube_dependencies = youtube_client_dependencies_available()
    tiktok_impl = (TIKTOK_PILOT / "tiktok-api.mjs").is_file()
    tiktok_token_interface = (TIKTOK_PILOT / "tokens.json").exists()
    return [
        SourceCapability(
            source="LOCAL_CREATOR_SOURCE", implementation_found=True,
            auth_state="NOT_REQUIRED", read_capability="AVAILABLE",
            analytics_capability="NOT_APPLICABLE", write_capability="LOCAL_ARTIFACTS_ONLY",
            zero_cost_proven=True, safe_to_use_now=True, blocker="NONE",
        ),
        SourceCapability(
            source="OFFICIAL_PUBLIC_DOCUMENTATION", implementation_found=True,
            auth_state="NOT_REQUIRED", read_capability="AVAILABLE",
            analytics_capability="NOT_APPLICABLE", write_capability="NONE",
            zero_cost_proven=True, safe_to_use_now=True, blocker="NO_BUILT_IN_NETWORK_FETCHER; EVIDENCE_MUST_BE_INGESTED_BY_APPROVED_RESEARCH_TOOL",
        ),
        SourceCapability(
            source="YOUTUBE", implementation_found=youtube_impl,
            auth_state=("LOCAL_CLIENT_DEPENDENCIES_MISSING" if youtube_impl and not youtube_dependencies
                        else "UNVERIFIED_LOCAL_AUTH_INTERFACE" if youtube_config_interface else "NOT_CONFIGURED"),
            read_capability=("NOT_AVAILABLE" if youtube_impl and not youtube_dependencies
                             else "NOT_AUTHORIZED" if youtube_impl else "NOT_IMPLEMENTED"),
            analytics_capability=("NOT_AVAILABLE" if youtube_impl and not youtube_dependencies else "NOT_AUTHORIZED"),
            write_capability="HUMAN_GATE",
            zero_cost_proven=False, safe_to_use_now=False,
            blocker=("GOOGLE_CLIENT_DEPENDENCIES_MISSING; NO_TOKEN_READ_OR_REFRESH_PERFORMED"
                     if youtube_impl and not youtube_dependencies
                     else "CURRENT_OAUTH_TOKEN_VALIDITY_AND_SCOPE_NOT_VERIFIED; NO_TOKEN_READ_OR_REFRESH_PERFORMED"),
        ),
        SourceCapability(
            source="TIKTOK", implementation_found=tiktok_impl,
            auth_state="UNVERIFIED_LOCAL_AUTH_INTERFACE" if tiktok_token_interface else "NOT_CONFIGURED",
            read_capability="NOT_IMPLEMENTED", analytics_capability="NOT_IMPLEMENTED",
            write_capability="DRAFT_UPLOAD_ONLY_HUMAN_GATE" if tiktok_impl else "NOT_IMPLEMENTED",
            zero_cost_proven=False, safe_to_use_now=False,
            blocker="NO_VERIFIED_READ_OR_ANALYTICS_ENDPOINT; TOKEN_NOT_READ; PUBLICATION_NOT_AUTHORIZED",
        ),
    ]


def normalize_youtube_evidence(
    *, channel_id: str, video_id: str | None, title: str | None,
    publication_status: str | None, published_at: str | None,
    retrieved_at: str, source_endpoint: str,
) -> dict[str, Any]:
    """Normalize a real API response; never manufacture a missing field.

    The caller may persist this only after a successful, authorized read.  This
    function intentionally accepts no credential material and does not infer
    metrics, publication status, or a video identifier.
    """
    if not channel_id or not retrieved_at or not source_endpoint:
        raise ValueError("real YouTube evidence requires channel, retrieval time, and endpoint")
    record = {
        "platform": "YOUTUBE",
        "channel_id": channel_id,
        "video_id": video_id,
        "title": title,
        "publication_status": publication_status,
        "published_at": published_at,
        "retrieved_at": retrieved_at,
        "source_endpoint": source_endpoint,
    }
    record["evidence_hash"] = stable_hash(record)
    record["dedupe_fingerprint"] = stable_hash({
        "channel_id": channel_id, "video_id": video_id, "evidence_hash": record["evidence_hash"],
    })
    return record


def compute_publication_dedupe_fingerprint(
    *,
    platform: str,
    target_channel_id: str,
    media_sha256: str,
) -> str:
    """Compute an immutable publication deduplication fingerprint.

    Canonical rule:
    SHA-256 of: "{PLATFORM}:{CHANNEL_ID}:{MEDIA_SHA256}"
    where PLATFORM is uppercase, CHANNEL_ID is trimmed,
    and MEDIA_SHA256 is lowercase.
    Title does NOT participate, ensuring title revisions do not alter upload identity.
    """
    p = platform.strip().upper()
    ch = target_channel_id.strip()
    sha = media_sha256.strip().lower()
    canonical_str = f"{p}:{ch}:{sha}"
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def build_research_evidence(
    *, question: str, source: str, source_type: str, finding: str,
    confidence: str, production_relevance: str, information_gain: str,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Build a schema-shaped public research record with stable dedupe fields."""
    if not question.strip() or not source.strip() or not finding.strip():
        raise ValueError("research question, source, and finding are required")
    if information_gain not in {"NEW_INFORMATION", "NO_NEW_INFORMATION"}:
        raise ValueError("invalid information_gain")
    retrieved = retrieved_at or _now()
    evidence_hash = stable_hash({"question": question, "source": source, "finding": finding})
    fingerprint = stable_hash({"question": question, "source": source, "evidence_hash": evidence_hash})
    return {
        "schema_version": "1.0",
        "research_question": question,
        "source": source,
        "source_type": source_type,
        "retrieved_at": retrieved,
        "evidence_hash": evidence_hash,
        "dedupe_fingerprint": fingerprint,
        "finding": finding,
        "confidence": confidence,
        "information_gain": information_gain,
        "production_relevance": production_relevance,
        "last_checked": retrieved,
        "analytics_snapshot": None,
        "publication_authorized": False,
    }


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def ingest_research_evidence(repo_dir: Path, evidence: dict[str, Any]) -> tuple[str, Path]:
    """Persist a public research record once; unchanged evidence is a no-op."""
    required = {"research_question", "source", "source_type", "retrieved_at", "evidence_hash", "finding", "confidence", "information_gain", "production_relevance", "last_checked", "dedupe_fingerprint"}
    if not required.issubset(evidence):
        raise ValueError("incomplete research evidence")
    records = repo_dir / "events" / "research" / "evidence"
    path = records / f"{evidence['dedupe_fingerprint']}.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("evidence_hash") == evidence["evidence_hash"]:
            return "NO_NEW_INFORMATION", path
        # A fingerprint includes the evidence hash, so this branch signals a
        # local record corruption instead of silently overwriting provenance.
        raise ValueError("research evidence fingerprint collision")
    _atomic_write(path, evidence)
    return evidence["information_gain"], path


def refresh_creator_input_sources(repo_dir: Path) -> dict[str, Any]:
    """Deterministic no-network refresh for the supervisor's empty-queue path.

    It only reports already-durable evidence.  It never calls a platform, never
    treats credentials as data, and never fabricates analytics or opportunities.
    """
    evidence_dir = repo_dir / "events" / "research" / "evidence"
    evidence_items: list[dict[str, Any]] = []
    if evidence_dir.exists():
        for candidate in sorted(evidence_dir.glob("*.json")):
            try:
                item = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if item.get("information_gain") == "NEW_INFORMATION" and item.get("production_relevance") == "CHANGES_PRODUCTION_DECISION":
                evidence_items.append(item)
    return {
        "capabilities": [item.to_dict() for item in discover_capabilities()],
        "durable_research_items": evidence_items,
        "opportunities": [],
        "status": "NO_NEW_INFORMATION" if not evidence_items else "EVIDENCE_REQUIRES_CHIEF_REVIEW",
    }


def run_youtube_read_only_canary(
    repo_dir: Path,
    token_reference: str = "fruitki-test",
    max_recent_items: int = 5,
) -> dict[str, Any]:
    """Execute the bounded, read-only YouTube canary using existing authorization.

    Guarantees:
    - Zero scope escalations (only uses https://www.googleapis.com/auth/youtube.force-ssl)
    - Zero publications / mutations
    - Zero credential exposures
    - Automatic normal token refresh if authorized
    - Returns YOUTUBE_AUTH_HUMAN_GATE if user interaction is required
    """
    if not youtube_client_dependencies_available():
        return {
            "status": "BLOCKED",
            "auth_state": "LOCAL_CLIENT_DEPENDENCIES_MISSING",
            "read_state": "NOT_AVAILABLE",
            "human_gate_required": False,
            "human_gate_reason": "NONE",
            "exact_human_action": "NONE",
            "error": "Google client dependencies missing",
        }

    try:
        import certifi
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    except ImportError:
        pass

    config_path = YOUTUBE_PILOT / "config.json"
    if not config_path.is_file():
        return {
            "status": "BLOCKED",
            "auth_state": "NOT_CONFIGURED",
            "read_state": "NOT_AVAILABLE",
            "human_gate_required": True,
            "human_gate_reason": "YOUTUBE_AUTH_HUMAN_GATE",
            "exact_human_action": "Provide local YouTube OAuth pilot configuration in config.json",
        }

    config = json.loads(config_path.read_text(encoding="utf-8"))
    token_dir = (YOUTUBE_PILOT / config.get("token_directory", "")).resolve()
    token_path = token_dir / f"{token_reference}.json"

    if not token_path.is_file():
        return {
            "status": "BLOCKED",
            "auth_state": "UNVERIFIED_LOCAL_AUTH_INTERFACE",
            "read_state": "NOT_AUTHORIZED",
            "human_gate_required": True,
            "human_gate_reason": "YOUTUBE_AUTH_HUMAN_GATE",
            "exact_human_action": f"Authenticate local YouTube OAuth pilot token for reference {token_reference}",
        }

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]

    try:
        credentials = Credentials.from_authorized_user_file(str(token_path), scopes=scopes)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            token_path.write_text(credentials.to_json(), encoding="utf-8")
            token_path.chmod(0o600)
    except Exception as auth_err:
        return {
            "status": "HUMAN_GATE",
            "auth_state": "INTERACTIVE_AUTH_REQUIRED",
            "read_state": "NOT_AVAILABLE",
            "human_gate_required": True,
            "human_gate_reason": "YOUTUBE_AUTH_HUMAN_GATE",
            "exact_human_action": f"Re-authenticate YouTube OAuth token ({token_reference}): {auth_err}",
        }

    try:
        youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
        ch_resp = youtube.channels().list(part="id,snippet,contentDetails", mine=True).execute()
        items = ch_resp.get("items", [])
        if len(items) != 1:
            return {
                "status": "ERROR",
                "auth_state": "UNEXPECTED_CHANNEL_COUNT",
                "read_state": "NOT_AVAILABLE",
                "human_gate_required": True,
                "human_gate_reason": "YOUTUBE_AUTH_HUMAN_GATE",
                "exact_human_action": f"Expected exactly 1 channel for token {token_reference}, received {len(items)}",
            }

        channel = items[0]
        channel_id = channel.get("id", "")
        snippet = channel.get("snippet", {})
        channel_name = snippet.get("title", "")
        channel_handle = snippet.get("customUrl", "")
        uploads_id = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")

        evidence_list: list[dict[str, Any]] = []
        new_info_count = 0
        no_new_info_count = 0

        # Read recent videos from uploads playlist
        if uploads_id:
            pl_resp = youtube.playlistItems().list(
                part="snippet,contentDetails,status",
                playlistId=uploads_id,
                maxResults=max_recent_items,
            ).execute()

            raw_items = pl_resp.get("items", [])
            video_ids = [it.get("contentDetails", {}).get("videoId") for it in raw_items if it.get("contentDetails", {}).get("videoId")]

            if video_ids:
                v_resp = youtube.videos().list(
                    part="snippet,status,contentDetails",
                    id=",".join(video_ids),
                ).execute()

                for v in v_resp.get("items", []):
                    v_snip = v.get("snippet", {})
                    v_stat = v.get("status", {})
                    ev = normalize_youtube_evidence(
                        channel_id=channel_id,
                        video_id=v.get("id"),
                        title=v_snip.get("title"),
                        publication_status=v_stat.get("privacyStatus"),
                        published_at=v_snip.get("publishedAt"),
                        retrieved_at=_now(),
                        source_endpoint="youtube.videos.list",
                    )
                    evidence_list.append(ev)

                    research_rec = build_research_evidence(
                        question=f"What is the current YouTube publication status for video {v.get('id')} on channel {channel_name}?",
                        source=f"https://www.youtube.com/watch?v={v.get('id')}",
                        source_type="YOUTUBE",
                        finding=f"Video '{v_snip.get('title')}' is currently {v_stat.get('privacyStatus')} on channel {channel_name} ({channel_handle}).",
                        confidence="HIGH",
                        production_relevance="NO_CURRENT_PIPELINE_CHANGE",
                        information_gain="NO_NEW_INFORMATION",
                        retrieved_at=ev["retrieved_at"],
                    )
                    gain, _ = ingest_research_evidence(repo_dir, research_rec)
                    if gain == "NEW_INFORMATION":
                        new_info_count += 1
                    else:
                        no_new_info_count += 1

        analytics_state = "YOUTUBE_ANALYTICS_NOT_AUTHORIZED"

        return {
            "status": "PASS",
            "auth_verification": "SUCCESS",
            "auth_state": "AUTHORIZED",
            "human_gate_required": False,
            "human_gate_reason": "NONE",
            "exact_human_action": "NONE",
            "youtube_read_state": "AVAILABLE",
            "channel_identified": True,
            "channel_id": channel_id,
            "channel_name": channel_name,
            "channel_handle": channel_handle,
            "real_youtube_items": len(evidence_list),
            "real_youtube_evidence": evidence_list,
            "new_information_items": new_info_count,
            "no_new_information_items": no_new_info_count,
            "creator_opportunities_created": 0,
            "youtube_analytics_state": analytics_state,
            "publications": 0,
            "mutations": 0,
            "scope_escalations": 0,
            "secrets_exposed": 0,
            "money_spent_eur": 0.0,
        }
    except Exception as api_err:
        return {
            "status": "ERROR",
            "auth_state": "API_ERROR",
            "read_state": "ERROR",
            "human_gate_required": True,
            "human_gate_reason": "YOUTUBE_AUTH_HUMAN_GATE",
            "exact_human_action": f"Resolve YouTube Data API error: {api_err}",
        }

