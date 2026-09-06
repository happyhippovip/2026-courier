#!/usr/bin/env python3
"""Evidence Provenance and Cryptographic Receipt System for FruitKI Publication.

Implements:
- ProductionAuthorizedYouTubeReadService: The ONLY authorized production ingestion service
  owning the full read lifecycle (credentials, API client, live requests, internal pagination,
  secret scrubbing, receipts, evidence, atomic persistence).
- TestFixtureYouTubeReadService: Separate, explicit fixture reader emitting trust_domain="TEST_FIXTURE".
- ProvenanceReceipt: Cryptographically bound receipt with explicit trust_domain:
    AUTHORIZED_PROVIDER_READ_OBSERVED | TEST_FIXTURE | LOCAL_DERIVED | HISTORICAL_UNVERIFIED
- Strong Provenance Bundle & Duplicate Preflight cryptographic binding.
- Strict internal pagination and fail-closed secret safety inspection.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent

CHANNEL_IDENTITY_MAX_AGE_SECONDS = 86400.0  # 24 hours
DUPLICATE_SNAPSHOT_MAX_AGE_SECONDS = 900.0   # 15 minutes
PROVENANCE_VERSION = "2.1"
TRUSTED_SERVICE_VERSION = "2.0"

YOUTUBE_PILOT_CONFIG_DIR = Path("/Users/user/Downloads/2026-Projektzentrale/02-YouTube-Operations/youtube-oauth-pilot")

FORBIDDEN_SECRET_KEYS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "client_id",
    "authorization",
    "cookie",
    "credentials",
    "oauth_code",
    "secret",
    "private_key",
}

SECRET_PATTERNS = [
    re.compile(r"ya29\.[0-9A-Za-z-_]+"),               # Google OAuth access token
    re.compile(r"1//[0-9A-Za-z-_]+"),                  # Google refresh token
    re.compile(r"GOCSPX-[0-9A-Za-z-_]{20,}"),          # Google client secret
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_for_secrets(obj: Any) -> tuple[bool, str | None]:
    """Inspect a data structure for any secret keys or token patterns.

    Returns (True, None) if clean, or (False, reason) if secret detected.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in FORBIDDEN_SECRET_KEYS:
                return False, f"Forbidden secret key detected: {k}"
            clean, reason = check_for_secrets(v)
            if not clean:
                return False, reason
    elif isinstance(obj, list):
        for item in obj:
            clean, reason = check_for_secrets(item)
            if not clean:
                return False, reason
    elif isinstance(obj, str):
        for pat in SECRET_PATTERNS:
            if pat.search(obj):
                return False, "OAuth token pattern detected in payload string"
    return True, None


class ProvenanceSource(str, Enum):
    ACTUAL_PROVIDER_READ = "ACTUAL_PROVIDER_READ"
    LOCAL_DERIVED = "LOCAL_DERIVED"
    TEST_FIXTURE = "TEST_FIXTURE"
    HISTORICAL_UNVERIFIED = "HISTORICAL_UNVERIFIED"


class TrustDomain(str, Enum):
    AUTHORIZED_PROVIDER_READ_OBSERVED = "AUTHORIZED_PROVIDER_READ_OBSERVED"
    TEST_FIXTURE = "TEST_FIXTURE"
    LOCAL_DERIVED = "LOCAL_DERIVED"
    HISTORICAL_UNVERIFIED = "HISTORICAL_UNVERIFIED"


@dataclass(frozen=True)
class ProvenanceReceipt:
    receipt_id: str
    provider: str  # "GOOGLE_YOUTUBE_API"
    platform: str  # "YOUTUBE"
    provenance_source: str  # ProvenanceSource
    operation: str  # "channels.list" | "playlistItems.list"
    endpoint: str  # "youtube.channels.list" | "youtube.playlistItems.list"
    request_parameters_safe: dict[str, Any]
    authenticated_channel_id: str
    scope_reference: str
    started_at: str
    completed_at: str
    result_count: int
    page_count: int
    payload_evidence_hash: str
    receipt_hash: str
    bundle_id: str = ""
    trust_domain: str = TrustDomain.AUTHORIZED_PROVIDER_READ_OBSERVED.value
    next_page_token_present: bool = False
    coverage_complete: bool = True
    provenance_version: str = PROVENANCE_VERSION
    trusted_service_version: str = TRUSTED_SERVICE_VERSION
    trusted_adapter_version: str | None = None
    previous_receipt_hash: str | None = None

    def __post_init__(self):
        if not self.trust_domain:
            if self.provenance_source == ProvenanceSource.ACTUAL_PROVIDER_READ.value:
                object.__setattr__(self, "trust_domain", TrustDomain.AUTHORIZED_PROVIDER_READ_OBSERVED.value)
            else:
                object.__setattr__(self, "trust_domain", TrustDomain.TEST_FIXTURE.value)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def _create_internal(
        cls,
        *,
        bundle_id: str,
        provider: str = "GOOGLE_YOUTUBE_API",
        platform: str = "YOUTUBE",
        provenance_source: str,
        trust_domain: str,
        operation: str,
        endpoint: str,
        request_parameters_safe: dict[str, Any],
        authenticated_channel_id: str,
        scope_reference: str,
        started_at: str,
        completed_at: str,
        result_count: int,
        page_count: int,
        next_page_token_present: bool,
        coverage_complete: bool,
        payload_evidence_hash: str,
        trusted_service_version: str = TRUSTED_SERVICE_VERSION,
        previous_receipt_hash: str | None = None,
    ) -> ProvenanceReceipt:
        receipt_id = f"rcpt-{uuid.uuid4().hex[:12]}"
        raw = {
            "receipt_id": receipt_id,
            "bundle_id": bundle_id,
            "provider": provider,
            "platform": platform,
            "provenance_source": provenance_source,
            "trust_domain": trust_domain,
            "operation": operation,
            "endpoint": endpoint,
            "request_parameters_safe": request_parameters_safe,
            "authenticated_channel_id": authenticated_channel_id,
            "scope_reference": scope_reference,
            "started_at": started_at,
            "completed_at": completed_at,
            "result_count": result_count,
            "page_count": page_count,
            "next_page_token_present": next_page_token_present,
            "coverage_complete": coverage_complete,
            "payload_evidence_hash": payload_evidence_hash,
            "provenance_version": PROVENANCE_VERSION,
            "trusted_service_version": trusted_service_version,
            "previous_receipt_hash": previous_receipt_hash,
        }
        receipt_hash = hashlib.sha256(
            json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return cls(receipt_id=receipt_id, receipt_hash=receipt_hash, **{k: v for k, v in raw.items() if k != "receipt_id"})

    @classmethod
    def create(
        cls,
        *,
        bundle_id: str | None = None,
        provider: str = "GOOGLE_YOUTUBE_API",
        platform: str = "YOUTUBE",
        provenance_source: str = ProvenanceSource.TEST_FIXTURE.value,
        trust_domain: str = TrustDomain.TEST_FIXTURE.value,
        operation: str,
        endpoint: str,
        request_parameters_safe: dict[str, Any],
        authenticated_channel_id: str,
        scope_reference: str,
        started_at: str,
        completed_at: str,
        result_count: int,
        page_count: int,
        next_page_token_present: bool,
        coverage_complete: bool,
        payload_evidence_hash: str,
        trusted_service_version: str = "FIXTURE_ADAPTER",
        previous_receipt_hash: str | None = None,
    ) -> ProvenanceReceipt:
        # Generic public builder CANNOT emit AUTHORIZED_PROVIDER_READ_OBSERVED
        if trust_domain == TrustDomain.AUTHORIZED_PROVIDER_READ_OBSERVED.value:
            raise PermissionError("Direct caller cannot forge AUTHORIZED_PROVIDER_READ_OBSERVED trust domain via generic builder")
        if provenance_source == ProvenanceSource.ACTUAL_PROVIDER_READ.value:
            raise PermissionError("Direct caller cannot forge ACTUAL_PROVIDER_READ provenance via generic builder")

        b_id = bundle_id or f"bundle-{uuid.uuid4().hex[:12]}"
        return cls._create_internal(
            bundle_id=b_id,
            provider=provider,
            platform=platform,
            provenance_source=provenance_source,
            trust_domain=trust_domain,
            operation=operation,
            endpoint=endpoint,
            request_parameters_safe=request_parameters_safe,
            authenticated_channel_id=authenticated_channel_id,
            scope_reference=scope_reference,
            started_at=started_at,
            completed_at=completed_at,
            result_count=result_count,
            page_count=page_count,
            next_page_token_present=next_page_token_present,
            coverage_complete=coverage_complete,
            payload_evidence_hash=payload_evidence_hash,
            trusted_service_version=trusted_service_version,
            previous_receipt_hash=previous_receipt_hash,
        )

    def verify_integrity(self) -> bool:
        clean, _ = check_for_secrets(self.to_dict())
        if not clean:
            return False

        # Support both current schema v2.1 and legacy schema v2.0
        if self.bundle_id:
            raw = {
                "receipt_id": self.receipt_id,
                "bundle_id": self.bundle_id,
                "provider": self.provider,
                "platform": self.platform,
                "provenance_source": self.provenance_source,
                "trust_domain": self.trust_domain,
                "operation": self.operation,
                "endpoint": self.endpoint,
                "request_parameters_safe": self.request_parameters_safe,
                "authenticated_channel_id": self.authenticated_channel_id,
                "scope_reference": self.scope_reference,
                "started_at": self.started_at,
                "completed_at": self.completed_at,
                "result_count": self.result_count,
                "page_count": self.page_count,
                "next_page_token_present": self.next_page_token_present,
                "coverage_complete": self.coverage_complete,
                "payload_evidence_hash": self.payload_evidence_hash,
                "provenance_version": self.provenance_version,
                "trusted_service_version": self.trusted_service_version,
                "previous_receipt_hash": self.previous_receipt_hash,
            }
        else:
            # Legacy 134G format
            raw = {
                "receipt_id": self.receipt_id,
                "provider": self.provider,
                "platform": self.platform,
                "provenance_source": self.provenance_source,
                "operation": self.operation,
                "endpoint": self.endpoint,
                "request_parameters_safe": self.request_parameters_safe,
                "authenticated_channel_id": self.authenticated_channel_id,
                "scope_reference": self.scope_reference,
                "started_at": self.started_at,
                "completed_at": self.completed_at,
                "result_count": self.result_count,
                "page_count": self.page_count,
                "next_page_token_present": self.next_page_token_present,
                "coverage_complete": self.coverage_complete,
                "payload_evidence_hash": self.payload_evidence_hash,
                "provenance_version": self.provenance_version,
                "trusted_adapter_version": self.trusted_adapter_version or "1.0",
                "previous_receipt_hash": self.previous_receipt_hash,
            }

        expected_hash = hashlib.sha256(
            json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return expected_hash == self.receipt_hash


def compute_payload_hash(payload_data: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of evidence payload excluding provenance wrapper fields."""
    raw = {k: v for k, v in payload_data.items() if k not in {
        "payload_evidence_hash", "authorized_read_receipt_id", "authorized_read_receipt_hash", "bundle_id"
    }}
    return hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


class ProductionAuthorizedYouTubeReadService:
    """The ONLY authorized production ingestion service."""

    @classmethod
    def _build_authenticated_youtube_client(cls, token_reference: str = "fruitki-test") -> Any:
        token_dir = YOUTUBE_PILOT_CONFIG_DIR / "tokens"
        token_path = token_dir / f"{token_reference}.json"

        if not token_path.is_file():
            raise FileNotFoundError(f"YouTube OAuth token file missing: {token_path}")

        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
        credentials = Credentials.from_authorized_user_file(str(token_path), scopes=scopes)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            token_path.write_text(credentials.to_json(), encoding="utf-8")
            token_path.chmod(0o600)

        return build("youtube", "v3", credentials=credentials, cache_discovery=False)

    @classmethod
    def capture_channel_evidence(
        cls,
        repo_dir: Path | None = None,
        *,
        token_reference: str = "fruitki-test",
    ) -> tuple[dict[str, Any], ProvenanceReceipt]:
        root = repo_dir or REPO_ROOT
        started_at = _now()
        youtube = cls._build_authenticated_youtube_client(token_reference=token_reference)

        resp = youtube.channels().list(part="id,snippet,contentDetails", mine=True).execute()
        completed_at = _now()

        if not isinstance(resp, dict) or resp.get("kind") != "youtube#channelListResponse":
            raise ValueError(f"Malformed channel API response: {resp}")

        items = resp.get("items", [])
        if not items:
            raise ValueError("No authenticated channel found in YouTube API response")

        ch_item = items[0]
        channel_id = ch_item.get("id", "")
        snippet = ch_item.get("snippet", {})
        channel_handle = snippet.get("customUrl", "")
        channel_title = snippet.get("title", "")
        content_details = ch_item.get("contentDetails", {})
        uploads_playlist_id = content_details.get("relatedPlaylists", {}).get("uploads", f"UU{channel_id[2:]}")

        bundle_id = f"bundle-ch-{uuid.uuid4().hex[:12]}"
        payload_core = {
            "schema_version": "2.0",
            "platform": "YOUTUBE",
            "channel_id": channel_id,
            "channel_handle": channel_handle,
            "channel_title": channel_title,
            "uploads_playlist_id": uploads_playlist_id,
            "endpoint": "youtube.channels.list",
            "retrieved_at": completed_at,
            "scope_reference": "https://www.googleapis.com/auth/youtube.force-ssl",
        }

        clean, reason = check_for_secrets(payload_core)
        if not clean:
            raise ValueError(f"Secret leakage detected in channel payload: {reason}")

        payload_hash = compute_payload_hash(payload_core)

        receipt = ProvenanceReceipt._create_internal(
            bundle_id=bundle_id,
            provider="GOOGLE_YOUTUBE_API",
            platform="YOUTUBE",
            provenance_source=ProvenanceSource.ACTUAL_PROVIDER_READ.value,
            trust_domain=TrustDomain.AUTHORIZED_PROVIDER_READ_OBSERVED.value,
            operation="channels.list",
            endpoint="youtube.channels.list",
            request_parameters_safe={"part": "id,snippet,contentDetails", "mine": True},
            authenticated_channel_id=channel_id,
            scope_reference="https://www.googleapis.com/auth/youtube.force-ssl",
            started_at=started_at,
            completed_at=completed_at,
            result_count=len(items),
            page_count=1,
            next_page_token_present=False,
            coverage_complete=True,
            payload_evidence_hash=payload_hash,
            trusted_service_version=TRUSTED_SERVICE_VERSION,
        )

        evidence = {
            **payload_core,
            "bundle_id": bundle_id,
            "payload_evidence_hash": payload_hash,
            "authorized_read_receipt_id": receipt.receipt_id,
            "authorized_read_receipt_hash": receipt.receipt_hash,
        }

        ev_file = root / "events" / "evidence" / "channel_evidence_fruitki.json"
        rcpt_file = root / "events" / "receipts" / f"{receipt.receipt_id}.json"
        bundle_file = root / "events" / "bundles" / f"{bundle_id}.json"
        bundle_manifest = {
            "schema_version": "2.0",
            "bundle_id": bundle_id,
            "provider": "GOOGLE_YOUTUBE_API",
            "platform": "YOUTUBE",
            "trust_domain": TrustDomain.AUTHORIZED_PROVIDER_READ_OBSERVED.value,
            "operation": "channels.list",
            "endpoint": "youtube.channels.list",
            "authenticated_channel_id": channel_id,
            "payload_evidence_hash": payload_hash,
            "receipt_id": receipt.receipt_id,
            "receipt_hash": receipt.receipt_hash,
            "committed_by_production_service": True,
            "committed_at": completed_at,
        }
        _atomic_write_json(ev_file, evidence)
        _atomic_write_json(rcpt_file, receipt.to_dict())
        _atomic_write_json(bundle_file, bundle_manifest)

        return evidence, receipt

    @classmethod
    def capture_upload_snapshot(
        cls,
        repo_dir: Path | None = None,
        *,
        token_reference: str = "fruitki-test",
        max_pages: int = 10,
        page_size: int = 50,
    ) -> tuple[dict[str, Any], ProvenanceReceipt]:
        root = repo_dir or REPO_ROOT
        started_at = _now()
        youtube = cls._build_authenticated_youtube_client(token_reference=token_reference)

        ch_resp = youtube.channels().list(part="id,contentDetails", mine=True).execute()
        items = ch_resp.get("items", [])
        if not items:
            raise ValueError("No authenticated channel found for upload snapshot")
        channel_id = items[0].get("id", "")
        uploads_playlist_id = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", f"UU{channel_id[2:]}")

        current_page_token: str | None = None
        seen_page_tokens: set[str] = set()
        pages_processed = 0
        video_ids_seen: list[str] = []
        safe_metadata: list[dict[str, Any]] = []
        coverage_complete = False
        next_page_token_present = False
        pagination_terminal_state = "UNKNOWN"

        while pages_processed < max_pages:
            req = youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=page_size,
                pageToken=current_page_token,
            )
            page_resp = req.execute()

            if not isinstance(page_resp, dict) or page_resp.get("kind") != "youtube#playlistItemListResponse":
                coverage_complete = False
                pagination_terminal_state = "PROVIDER_ERROR"
                break

            pages_processed += 1
            page_items = page_resp.get("items", [])
            for it in page_items:
                v_id = it.get("contentDetails", {}).get("videoId")
                if v_id and v_id not in video_ids_seen:
                    video_ids_seen.append(v_id)
                snippet = it.get("snippet", {})
                safe_metadata.append({
                    "video_id": v_id,
                    "title": snippet.get("title", ""),
                    "published_at": snippet.get("publishedAt", ""),
                })

            next_tok = page_resp.get("nextPageToken")
            if next_tok is not None and not isinstance(next_tok, str):
                coverage_complete = False
                pagination_terminal_state = "MALFORMED_TOKEN"
                break

            if next_tok and next_tok.strip():
                clean_tok = next_tok.strip()
                if clean_tok in seen_page_tokens:
                    coverage_complete = False
                    pagination_terminal_state = "REPEATED_TOKEN"
                    break
                seen_page_tokens.add(clean_tok)
                current_page_token = clean_tok
                next_page_token_present = True
            else:
                coverage_complete = True
                next_page_token_present = False
                if len(video_ids_seen) == 0:
                    pagination_terminal_state = "ZERO_ITEM_TERMINAL"
                elif pages_processed == 1:
                    pagination_terminal_state = "ONE_PAGE_TERMINAL"
                else:
                    pagination_terminal_state = "MULTI_PAGE_TERMINAL"
                break

        if not coverage_complete and pagination_terminal_state == "UNKNOWN":
            pagination_terminal_state = "PAGE_LIMIT_EXCEEDED"

        completed_at = _now()
        bundle_id = f"bundle-snap-{uuid.uuid4().hex[:12]}"
        payload_core = {
            "schema_version": "2.0",
            "platform": "YOUTUBE",
            "channel_id": channel_id,
            "uploads_playlist_id": uploads_playlist_id,
            "endpoint": "youtube.playlistItems.list",
            "retrieved_at": completed_at,
            "scope_reference": "https://www.googleapis.com/auth/youtube.force-ssl",
            "items_checked": len(video_ids_seen),
            "page_count": pages_processed,
            "coverage_complete": coverage_complete,
            "pagination_terminal_state": pagination_terminal_state,
            "video_ids": video_ids_seen,
            "recent_items_metadata": safe_metadata,
        }

        clean, reason = check_for_secrets(payload_core)
        if not clean:
            raise ValueError(f"Secret leakage detected in upload snapshot: {reason}")

        payload_hash = compute_payload_hash(payload_core)

        receipt = ProvenanceReceipt._create_internal(
            bundle_id=bundle_id,
            provider="GOOGLE_YOUTUBE_API",
            platform="YOUTUBE",
            provenance_source=ProvenanceSource.ACTUAL_PROVIDER_READ.value,
            trust_domain=TrustDomain.AUTHORIZED_PROVIDER_READ_OBSERVED.value,
            operation="playlistItems.list",
            endpoint="youtube.playlistItems.list",
            request_parameters_safe={
                "part": "snippet,contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": page_size,
            },
            authenticated_channel_id=channel_id,
            scope_reference="https://www.googleapis.com/auth/youtube.force-ssl",
            started_at=started_at,
            completed_at=completed_at,
            result_count=len(video_ids_seen),
            page_count=pages_processed,
            next_page_token_present=next_page_token_present,
            coverage_complete=coverage_complete,
            payload_evidence_hash=payload_hash,
            trusted_service_version=TRUSTED_SERVICE_VERSION,
        )

        evidence = {
            **payload_core,
            "bundle_id": bundle_id,
            "payload_evidence_hash": payload_hash,
            "authorized_read_receipt_id": receipt.receipt_id,
            "authorized_read_receipt_hash": receipt.receipt_hash,
        }

        ev_file = root / "events" / "evidence" / "youtube_uploads_snapshot_fruitki.json"
        rcpt_file = root / "events" / "receipts" / f"{receipt.receipt_id}.json"
        bundle_file = root / "events" / "bundles" / f"{bundle_id}.json"
        bundle_manifest = {
            "schema_version": "2.0",
            "bundle_id": bundle_id,
            "provider": "GOOGLE_YOUTUBE_API",
            "platform": "YOUTUBE",
            "trust_domain": TrustDomain.AUTHORIZED_PROVIDER_READ_OBSERVED.value,
            "operation": "playlistItems.list",
            "endpoint": "youtube.playlistItems.list",
            "authenticated_channel_id": channel_id,
            "payload_evidence_hash": payload_hash,
            "receipt_id": receipt.receipt_id,
            "receipt_hash": receipt.receipt_hash,
            "committed_by_production_service": True,
            "committed_at": completed_at,
        }
        _atomic_write_json(ev_file, evidence)
        _atomic_write_json(rcpt_file, receipt.to_dict())
        _atomic_write_json(bundle_file, bundle_manifest)

        return evidence, receipt


class TestFixtureYouTubeReadService:
    """Test fixture ingestion service emitting explicitly separated trust_domain="TEST_FIXTURE"."""

    @classmethod
    def create_channel_fixture(
        cls,
        *,
        channel_id: str = "UCg0O_a10jsQ74ffS_HgFGqA",
        channel_handle: str = "@kifruchtefilme",
        channel_title: str = "FruitKI",
        started_at: str | None = None,
        retrieved_at: str | None = None,
    ) -> tuple[dict[str, Any], ProvenanceReceipt]:
        start_ts = started_at or _now()
        retrieved_ts = retrieved_at or _now()
        bundle_id = f"bundle-fix-ch-{uuid.uuid4().hex[:12]}"
        uploads_playlist_id = f"UU{channel_id[2:]}"

        payload_core = {
            "schema_version": "2.0",
            "platform": "YOUTUBE",
            "channel_id": channel_id,
            "channel_handle": channel_handle,
            "channel_title": channel_title,
            "uploads_playlist_id": uploads_playlist_id,
            "endpoint": "youtube.channels.list",
            "retrieved_at": retrieved_ts,
            "scope_reference": "https://www.googleapis.com/auth/youtube.force-ssl",
        }
        payload_hash = compute_payload_hash(payload_core)

        receipt = ProvenanceReceipt._create_internal(
            bundle_id=bundle_id,
            provider="GOOGLE_YOUTUBE_API",
            platform="YOUTUBE",
            provenance_source=ProvenanceSource.TEST_FIXTURE.value,
            trust_domain=TrustDomain.TEST_FIXTURE.value,
            operation="channels.list",
            endpoint="youtube.channels.list",
            request_parameters_safe={"part": "id,snippet,contentDetails", "mine": True},
            authenticated_channel_id=channel_id,
            scope_reference="https://www.googleapis.com/auth/youtube.force-ssl",
            started_at=start_ts,
            completed_at=retrieved_ts,
            result_count=1,
            page_count=1,
            next_page_token_present=False,
            coverage_complete=True,
            payload_evidence_hash=payload_hash,
            trusted_service_version="FIXTURE_ADAPTER",
        )

        evidence = {
            **payload_core,
            "bundle_id": bundle_id,
            "payload_evidence_hash": payload_hash,
            "authorized_read_receipt_id": receipt.receipt_id,
            "authorized_read_receipt_hash": receipt.receipt_hash,
        }
        return evidence, receipt

    @classmethod
    def create_upload_snapshot_fixture(
        cls,
        *,
        channel_id: str = "UCg0O_a10jsQ74ffS_HgFGqA",
        video_ids: list[str] | None = None,
        recent_metadata: list[dict[str, Any]] | None = None,
        page_count: int = 1,
        coverage_complete: bool = True,
        next_page_token_present: bool = False,
        started_at: str | None = None,
        retrieved_at: str | None = None,
    ) -> tuple[dict[str, Any], ProvenanceReceipt]:
        start_ts = started_at or _now()
        retrieved_ts = retrieved_at or _now()
        bundle_id = f"bundle-fix-snap-{uuid.uuid4().hex[:12]}"
        uploads_playlist_id = f"UU{channel_id[2:]}"
        v_ids = video_ids if video_ids is not None else ["VID_FIXTURE_001", "VID_FIXTURE_002"]
        meta = recent_metadata if recent_metadata is not None else [{"video_id": vid, "title": f"Fixture {vid}"} for vid in v_ids]

        payload_core = {
            "schema_version": "2.0",
            "platform": "YOUTUBE",
            "channel_id": channel_id,
            "uploads_playlist_id": uploads_playlist_id,
            "endpoint": "youtube.playlistItems.list",
            "retrieved_at": retrieved_ts,
            "scope_reference": "https://www.googleapis.com/auth/youtube.force-ssl",
            "items_checked": len(v_ids),
            "page_count": page_count,
            "coverage_complete": coverage_complete,
            "video_ids": v_ids,
            "recent_items_metadata": meta,
        }
        payload_hash = compute_payload_hash(payload_core)

        receipt = ProvenanceReceipt._create_internal(
            bundle_id=bundle_id,
            provider="GOOGLE_YOUTUBE_API",
            platform="YOUTUBE",
            provenance_source=ProvenanceSource.TEST_FIXTURE.value,
            trust_domain=TrustDomain.TEST_FIXTURE.value,
            operation="playlistItems.list",
            endpoint="youtube.playlistItems.list",
            request_parameters_safe={"part": "snippet,contentDetails", "playlistId": uploads_playlist_id},
            authenticated_channel_id=channel_id,
            scope_reference="https://www.googleapis.com/auth/youtube.force-ssl",
            started_at=start_ts,
            completed_at=retrieved_ts,
            result_count=len(v_ids),
            page_count=page_count,
            next_page_token_present=next_page_token_present,
            coverage_complete=coverage_complete,
            payload_evidence_hash=payload_hash,
            trusted_service_version="FIXTURE_ADAPTER",
        )

        evidence = {
            **payload_core,
            "bundle_id": bundle_id,
            "payload_evidence_hash": payload_hash,
            "authorized_read_receipt_id": receipt.receipt_id,
            "authorized_read_receipt_hash": receipt.receipt_hash,
        }
        return evidence, receipt

    @classmethod
    def ingest_channel_response(
        cls,
        raw_response: dict[str, Any],
        *,
        started_at: str | None = None,
        retrieved_at: str | None = None,
    ) -> tuple[dict[str, Any], ProvenanceReceipt]:
        if not isinstance(raw_response, dict) or raw_response.get("kind") != "youtube#channelListResponse":
            raise ValueError(f"Malformed raw channel API response: {raw_response}")
        items = raw_response.get("items", [])
        if not items:
            raise ValueError("No authenticated channel found in response")
        ch = items[0]
        ch_id = ch.get("id", "UCg0O_a10jsQ74ffS_HgFGqA")
        snippet = ch.get("snippet", {})
        content_details = ch.get("contentDetails", {})
        uploads_id = content_details.get("relatedPlaylists", {}).get("uploads", f"UU{ch_id[2:]}")

        start_ts = started_at or _now()
        retrieved_ts = retrieved_at or _now()
        bundle_id = f"bundle-adapter-ch-{uuid.uuid4().hex[:12]}"
        payload_core = {
            "schema_version": "2.0",
            "platform": "YOUTUBE",
            "channel_id": ch_id,
            "channel_handle": snippet.get("customUrl", "@kifruchtefilme"),
            "channel_title": snippet.get("title", "FruitKI"),
            "uploads_playlist_id": uploads_id,
            "endpoint": "youtube.channels.list",
            "retrieved_at": retrieved_ts,
            "scope_reference": "https://www.googleapis.com/auth/youtube.force-ssl",
        }
        payload_hash = compute_payload_hash(payload_core)

        receipt = ProvenanceReceipt._create_internal(
            bundle_id=bundle_id,
            provider="GOOGLE_YOUTUBE_API",
            platform="YOUTUBE",
            provenance_source=ProvenanceSource.TEST_FIXTURE.value,
            trust_domain=TrustDomain.TEST_FIXTURE.value,
            operation="channels.list",
            endpoint="youtube.channels.list",
            request_parameters_safe={"part": "id,snippet,contentDetails", "mine": True},
            authenticated_channel_id=ch_id,
            scope_reference="https://www.googleapis.com/auth/youtube.force-ssl",
            started_at=start_ts,
            completed_at=retrieved_ts,
            result_count=len(items),
            page_count=1,
            next_page_token_present=False,
            coverage_complete=True,
            payload_evidence_hash=payload_hash,
            trusted_service_version="1.0",
        )
        evidence = {
            **payload_core,
            "bundle_id": bundle_id,
            "payload_evidence_hash": payload_hash,
            "authorized_read_receipt_id": receipt.receipt_id,
            "authorized_read_receipt_hash": receipt.receipt_hash,
        }
        return evidence, receipt

    @classmethod
    def ingest_uploads_paginated_reader(
        cls,
        fetch_page_fn: Any,
        *,
        channel_id: str = "UCg0O_a10jsQ74ffS_HgFGqA",
        uploads_playlist_id: str | None = None,
        started_at: str | None = None,
        retrieved_at: str | None = None,
        max_pages: int = 10,
    ) -> tuple[dict[str, Any], ProvenanceReceipt]:
        start_ts = started_at or _now()
        up_id = uploads_playlist_id or f"UU{channel_id[2:]}"
        cur_tok: str | None = None
        seen_toks: set[str] = set()
        pages_processed = 0
        video_ids_seen: list[str] = []
        safe_meta: list[dict[str, Any]] = []
        coverage_complete = False
        next_tok_present = False
        pagination_terminal_state = "UNKNOWN"

        while pages_processed < max_pages:
            try:
                page_resp = fetch_page_fn(cur_tok) if callable(fetch_page_fn) else {}
            except Exception:
                coverage_complete = False
                pagination_terminal_state = "PROVIDER_ERROR"
                break

            if not isinstance(page_resp, dict) or page_resp.get("kind") != "youtube#playlistItemListResponse":
                coverage_complete = False
                pagination_terminal_state = "PROVIDER_ERROR"
                break

            pages_processed += 1
            for it in page_resp.get("items", []):
                vid = it.get("contentDetails", {}).get("videoId")
                if vid and vid not in video_ids_seen:
                    video_ids_seen.append(vid)
                snippet = it.get("snippet", {})
                safe_meta.append({
                    "video_id": vid,
                    "title": snippet.get("title", ""),
                })

            next_tok = page_resp.get("nextPageToken")
            if next_tok is not None and not isinstance(next_tok, str):
                coverage_complete = False
                pagination_terminal_state = "MALFORMED_TOKEN"
                break

            if next_tok and str(next_tok).strip():
                clean_tok = str(next_tok).strip()
                if clean_tok in seen_toks:
                    coverage_complete = False
                    pagination_terminal_state = "REPEATED_TOKEN"
                    break
                seen_toks.add(clean_tok)
                cur_tok = clean_tok
                next_tok_present = True
            else:
                coverage_complete = True
                next_tok_present = False
                if len(video_ids_seen) == 0:
                    pagination_terminal_state = "ZERO_ITEM_TERMINAL"
                elif pages_processed == 1:
                    pagination_terminal_state = "ONE_PAGE_TERMINAL"
                else:
                    pagination_terminal_state = "MULTI_PAGE_TERMINAL"
                break

        if not coverage_complete and pagination_terminal_state == "UNKNOWN":
            pagination_terminal_state = "PAGE_LIMIT_EXCEEDED"

        retrieved_ts = retrieved_at or _now()
        bundle_id = f"bundle-adapter-snap-{uuid.uuid4().hex[:12]}"
        payload_core = {
            "schema_version": "2.0",
            "platform": "YOUTUBE",
            "channel_id": channel_id,
            "uploads_playlist_id": up_id,
            "endpoint": "youtube.playlistItems.list",
            "retrieved_at": retrieved_ts,
            "scope_reference": "https://www.googleapis.com/auth/youtube.force-ssl",
            "items_checked": len(video_ids_seen),
            "page_count": pages_processed,
            "coverage_complete": coverage_complete,
            "pagination_terminal_state": pagination_terminal_state,
            "video_ids": video_ids_seen,
            "recent_items_metadata": safe_meta,
        }
        payload_hash = compute_payload_hash(payload_core)

        receipt = ProvenanceReceipt._create_internal(
            bundle_id=bundle_id,
            provider="GOOGLE_YOUTUBE_API",
            platform="YOUTUBE",
            provenance_source=ProvenanceSource.TEST_FIXTURE.value,
            trust_domain=TrustDomain.TEST_FIXTURE.value,
            operation="playlistItems.list",
            endpoint="youtube.playlistItems.list",
            request_parameters_safe={"part": "snippet,contentDetails", "playlistId": up_id},
            authenticated_channel_id=channel_id,
            scope_reference="https://www.googleapis.com/auth/youtube.force-ssl",
            started_at=start_ts,
            completed_at=retrieved_ts,
            result_count=len(video_ids_seen),
            page_count=pages_processed,
            next_page_token_present=next_tok_present,
            coverage_complete=coverage_complete,
            payload_evidence_hash=payload_hash,
            trusted_service_version="1.0",
        )
        evidence = {
            **payload_core,
            "bundle_id": bundle_id,
            "payload_evidence_hash": payload_hash,
            "authorized_read_receipt_id": receipt.receipt_id,
            "authorized_read_receipt_hash": receipt.receipt_hash,
        }
        return evidence, receipt


TrustedYouTubeResponseAdapter = TestFixtureYouTubeReadService


def build_channel_evidence_package(
    *,
    channel_id: str = "UCg0O_a10jsQ74ffS_HgFGqA",
    channel_handle: str = "@kifruchtefilme",
    channel_title: str = "FruitKI",
    uploads_playlist_id: str = "UUg0O_a10jsQ74ffS_HgFGqA",
    provenance_source: str = ProvenanceSource.TEST_FIXTURE.value,
    trust_domain: str = TrustDomain.TEST_FIXTURE.value,
    retrieved_at: str | None = None,
    started_at: str | None = None,
) -> tuple[dict[str, Any], ProvenanceReceipt]:
    """Helper for test builders generating channel evidence package."""
    if (
        provenance_source == ProvenanceSource.ACTUAL_PROVIDER_READ.value
        or trust_domain == TrustDomain.AUTHORIZED_PROVIDER_READ_OBSERVED.value
    ):
        raise PermissionError("Generic builder cannot emit ACTUAL_PROVIDER_READ or AUTHORIZED_PROVIDER_READ_OBSERVED")
    return TestFixtureYouTubeReadService.create_channel_fixture(
        channel_id=channel_id,
        channel_handle=channel_handle,
        channel_title=channel_title,
        started_at=started_at,
        retrieved_at=retrieved_at,
    )


def build_upload_snapshot_evidence_package(
    *,
    channel_id: str = "UCg0O_a10jsQ74ffS_HgFGqA",
    uploads_playlist_id: str = "UUg0O_a10jsQ74ffS_HgFGqA",
    video_ids: list[str] | None = None,
    items_checked: int | None = None,
    page_count: int = 1,
    coverage_complete: bool = True,
    next_page_token_present: bool = False,
    provenance_source: str = ProvenanceSource.TEST_FIXTURE.value,
    trust_domain: str = TrustDomain.TEST_FIXTURE.value,
    retrieved_at: str | None = None,
    started_at: str | None = None,
) -> tuple[dict[str, Any], ProvenanceReceipt]:
    """Helper for test builders generating upload snapshot package."""
    if (
        provenance_source == ProvenanceSource.ACTUAL_PROVIDER_READ.value
        or trust_domain == TrustDomain.AUTHORIZED_PROVIDER_READ_OBSERVED.value
    ):
        raise PermissionError("Generic builder cannot emit ACTUAL_PROVIDER_READ or AUTHORIZED_PROVIDER_READ_OBSERVED")
    return TestFixtureYouTubeReadService.create_upload_snapshot_fixture(
        channel_id=channel_id,
        video_ids=video_ids,
        page_count=page_count,
        coverage_complete=coverage_complete,
        next_page_token_present=next_page_token_present,
        started_at=started_at,
        retrieved_at=retrieved_at,
    )


build_youtube_uploads_snapshot_package = build_upload_snapshot_evidence_package


def build_package_duplicate_preflight(
    *,
    publication_fingerprint: str,
    media_sha256: str,
    target_channel_id: str,
    channel_evidence_hash: str,
    channel_receipt_hash: str,
    upload_snapshot_hash: str,
    upload_snapshot_receipt_hash: str,
    items_checked: int,
    page_count: int,
    coverage_complete: bool,
    duplicate_match: bool,
    checked_at: str | None = None,
) -> dict[str, Any]:
    """Generate package-bound duplicate preflight result with cryptographic linking."""
    ts = checked_at or _now()
    if not coverage_complete:
        result = "PLATFORM_METADATA_CHECK_INCOMPLETE"
    elif duplicate_match:
        result = "PLATFORM_METADATA_MATCH_FOUND"
    else:
        result = "PLATFORM_METADATA_NO_MATCH_FOUND"

    record = {
        "schema_version": "2.0",
        "result": result,
        "publication_fingerprint": publication_fingerprint,
        "media_sha256": media_sha256,
        "target_channel_id": target_channel_id,
        "channel_evidence_hash": channel_evidence_hash,
        "channel_receipt_hash": channel_receipt_hash,
        "upload_snapshot_hash": upload_snapshot_hash,
        "upload_snapshot_receipt_hash": upload_snapshot_receipt_hash,
        "items_checked": items_checked,
        "page_count": page_count,
        "coverage_complete": coverage_complete,
        "checked_at": ts,
    }

    clean, reason = check_for_secrets(record)
    if not clean:
        raise ValueError(f"Secret leakage detected in preflight: {reason}")

    return record
