#!/usr/bin/env python3
"""Creator Factory Canonical Asset Inventory.

Discovers and models existing creator media assets, packaging status,
QC verdicts, audience status, and publication authorization states from
canonical local sources without making external calls or inventing unproven state.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

INVENTORY_SCHEMA_VERSION = "1.0"


def _compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1048576):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_canonical_asset_state_hash(data: dict[str, Any]) -> str:
    """Compute a deterministic hash over canonical asset state fields."""
    key_fields = {
        "content_id": str(data.get("content_id", "")),
        "product_family": str(data.get("product_family", "")),
        "media_sha256": str(data.get("media_sha256", "")).lower(),
        "qc_status": str(data.get("qc_status", "")),
        "target_platform": str(data.get("target_platform", "")),
        "target_channel_id": str(data.get("target_channel_id", "")),
        "audience_state": str(data.get("audience_state", "")),
        "publication_authorized": data.get("publication_authorized"),
        "current_technical_readiness_state": str(data.get("current_technical_readiness_state", "")),
        "current_blocking_gate": str(data.get("current_blocking_gate", "")),
        "immutable_content_fingerprint": str(data.get("immutable_content_fingerprint", "")),
    }
    raw = json.dumps(key_fields, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CreatorAssetRecord:
    """Deterministic model of a discovered Creator Factory asset."""

    schema_version: str
    content_id: str
    product_family: str
    media_master_path: str
    media_sha256: str
    duration_seconds: float | None
    resolution: str | None
    qc_status: str  # "PASS" | "FAIL" | "NOT_AVAILABLE"
    qc_report_path: str | None
    publish_package_path: str | None
    target_platform: str | None
    target_channel_id: str | None
    target_channel_handle: str | None
    audience_state: str  # "DECISION_REQUIRED" | "MADE_FOR_KIDS" | "NOT_MADE_FOR_KIDS" | "NOT_AVAILABLE"
    publication_authorized: bool | None
    current_technical_readiness_state: str
    current_blocking_gate: str
    evidence_timestamp: str | None
    immutable_content_fingerprint: str | None
    last_deterministic_verification_timestamp: str
    source_files: list[str]
    asset_state_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CreatorAssetInventory:
    """Canonical collection of discovered creator assets."""

    schema_version: str
    inventory_id: str
    generated_at: str
    assets: dict[str, CreatorAssetRecord]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "inventory_id": self.inventory_id,
            "generated_at": self.generated_at,
            "assets": {k: v.to_dict() for k, v in self.assets.items()},
        }


class CreatorAssetInventoryBuilder:
    """Discovers and verifies local creator assets from canonical file structures."""

    def __init__(self, repo_dir: Path | None = None):
        self.repo_dir = repo_dir or REPO_ROOT

    def scan_content_directory(
        self,
        content_root: Path | None = None,
        content_ids: list[str] | None = None,
        verification_timestamp: str = "2026-08-31T12:00:00.000000+00:00",
    ) -> CreatorAssetInventory:
        """Scan content directory and build canonical asset records."""
        root = content_root or (self.repo_dir / "runtime" / "content")
        assets: dict[str, CreatorAssetRecord] = {}

        if not root.is_dir():
            return CreatorAssetInventory(
                schema_version=INVENTORY_SCHEMA_VERSION,
                inventory_id=hashlib.sha256(b"empty").hexdigest(),
                generated_at=verification_timestamp,
                assets={},
            )

        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            if content_ids is not None and child.name not in content_ids:
                continue

            record = self._inspect_asset_dir(child, verification_timestamp)
            if record is not None:
                assets[record.content_id] = record

        # Deterministic inventory ID from sorted asset state hashes
        combined_hashes = "".join(
            f"{cid}:{assets[cid].asset_state_hash};" for cid in sorted(assets.keys())
        )
        inv_id = hashlib.sha256(combined_hashes.encode("utf-8")).hexdigest()

        return CreatorAssetInventory(
            schema_version=INVENTORY_SCHEMA_VERSION,
            inventory_id=inv_id,
            generated_at=verification_timestamp,
            assets=assets,
        )

    def _inspect_asset_dir(
        self,
        asset_dir: Path,
        verification_timestamp: str,
    ) -> CreatorAssetRecord | None:
        """Inspect a content subdirectory and extract proven facts."""
        content_id = asset_dir.name
        source_files: list[str] = []

        # 1. Look for media files (.mp4, .avi, .mov)
        media_candidates = sorted(
            list(asset_dir.glob("*.mp4")) + list(asset_dir.glob("*.avi")) + list(asset_dir.glob("*.mov"))
        )
        # Filter out temporary or partial files
        media_candidates = [m for m in media_candidates if not m.name.startswith(".")]

        if not media_candidates:
            # No media present -> incomplete
            return None

        # Preferred primary media master
        primary_media = media_candidates[0]
        for m in media_candidates:
            if "fruitki" in m.name or "render" in m.name or "master" in m.name:
                primary_media = m
                break

        source_files.append(str(primary_media.relative_to(self.repo_dir) if primary_media.is_relative_to(self.repo_dir) else primary_media))
        media_sha256 = _compute_file_sha256(primary_media)

        # 2. Look for render_metadata.json
        render_meta_path = asset_dir / "render_metadata.json"
        duration_seconds: float | None = None
        resolution: str | None = None

        if render_meta_path.is_file():
            source_files.append(str(render_meta_path.relative_to(self.repo_dir) if render_meta_path.is_relative_to(self.repo_dir) else render_meta_path))
            try:
                rmeta = json.loads(render_meta_path.read_text(encoding="utf-8"))
                duration_seconds = rmeta.get("mp4_duration_seconds") or rmeta.get("duration_seconds")
                probe = rmeta.get("mp4_probe") or {}
                if probe.get("width") and probe.get("height"):
                    resolution = f"{probe['width']}x{probe['height']}"
            except Exception:
                pass

        # 3. Look for qc_report.json
        qc_report_path = asset_dir / "qc_report.json"
        qc_status = "NOT_AVAILABLE"
        qc_report_ref: str | None = None

        if qc_report_path.is_file():
            qc_report_ref = str(qc_report_path.relative_to(self.repo_dir) if qc_report_path.is_relative_to(self.repo_dir) else qc_report_path)
            source_files.append(qc_report_ref)
            try:
                qc_data = json.loads(qc_report_path.read_text(encoding="utf-8"))
                if qc_data.get("source_hash") == media_sha256:
                    qc_status = str(qc_data.get("verdict", "NOT_AVAILABLE"))
                    if duration_seconds is None and qc_data.get("duration_seconds") is not None:
                        duration_seconds = float(qc_data["duration_seconds"])
                    vprobe = qc_data.get("video") or {}
                    if resolution is None and vprobe.get("width") and vprobe.get("height"):
                        resolution = f"{vprobe['width']}x{vprobe['height']}"
                else:
                    qc_status = "FAIL"
            except Exception:
                qc_status = "FAIL"

        # 4. Look for publish_package.json
        pkg_path = asset_dir / "publish_package.json"
        pkg_ref: str | None = None
        target_platform: str | None = None
        target_channel_id: str | None = None
        target_channel_handle: str | None = None
        audience_state = "NOT_AVAILABLE"
        publication_authorized: bool | None = None
        immutable_fingerprint: str | None = None
        evidence_timestamp: str | None = None
        product_family = "fruitki" if "fruitki" in content_id or "short" in content_id else "unknown"

        if pkg_path.is_file():
            pkg_ref = str(pkg_path.relative_to(self.repo_dir) if pkg_path.is_relative_to(self.repo_dir) else pkg_path)
            source_files.append(pkg_ref)
            try:
                pkg_data = json.loads(pkg_path.read_text(encoding="utf-8"))
                target_platform = pkg_data.get("platform")
                target_channel_id = pkg_data.get("target_channel_id")
                target_channel_handle = pkg_data.get("target_channel_handle")
                audience_raw = pkg_data.get("audience_decision")
                if audience_raw in {"DECISION_REQUIRED", "MADE_FOR_KIDS", "NOT_MADE_FOR_KIDS"}:
                    audience_state = audience_raw
                else:
                    audience_state = "NOT_AVAILABLE"

                # publication_authorized MUST strictly be boolean if present
                raw_auth = pkg_data.get("publication_authorized")
                if isinstance(raw_auth, bool):
                    publication_authorized = raw_auth
                else:
                    publication_authorized = None

                immutable_fingerprint = pkg_data.get("publication_dedupe_fingerprint")
                evidence_timestamp = pkg_data.get("prepared_at") or pkg_data.get("channel_verified_at")
            except Exception:
                pass

        # 5. Determine Technical Readiness and Current Blocking Gate
        if not pkg_ref:
            current_technical_readiness = "MEDIA_RENDERED_UNPACKAGED"
            current_blocking_gate = "PACKAGING_REQUIRED" if qc_status == "PASS" else "QC_REQUIRED"
        elif qc_status != "PASS":
            current_technical_readiness = "QC_PENDING"
            current_blocking_gate = "QC_REQUIRED"
        elif audience_state == "DECISION_REQUIRED" or audience_state == "NOT_AVAILABLE":
            current_technical_readiness = "COMPLETE_READY_FOR_REVIEW"
            current_blocking_gate = "AUDIENCE_DECISION_GATE"
        elif publication_authorized is not True:
            current_technical_readiness = "COMPLETE_READY_FOR_REVIEW"
            current_blocking_gate = "PUBLICATION_APPROVAL_GATE"
        else:
            current_technical_readiness = "READY_FOR_DISPATCH"
            current_blocking_gate = "NONE"

        # 6. Build state hash
        state_dict = {
            "content_id": content_id,
            "product_family": product_family,
            "media_sha256": media_sha256,
            "qc_status": qc_status,
            "target_platform": target_platform,
            "target_channel_id": target_channel_id,
            "audience_state": audience_state,
            "publication_authorized": publication_authorized,
            "current_technical_readiness_state": current_technical_readiness,
            "current_blocking_gate": current_blocking_gate,
            "immutable_content_fingerprint": immutable_fingerprint,
        }
        asset_state_hash = compute_canonical_asset_state_hash(state_dict)

        return CreatorAssetRecord(
            schema_version=INVENTORY_SCHEMA_VERSION,
            content_id=content_id,
            product_family=product_family,
            media_master_path=str(primary_media.relative_to(self.repo_dir) if primary_media.is_relative_to(self.repo_dir) else primary_media),
            media_sha256=media_sha256,
            duration_seconds=duration_seconds,
            resolution=resolution,
            qc_status=qc_status,
            qc_report_path=qc_report_ref,
            publish_package_path=pkg_ref,
            target_platform=target_platform,
            target_channel_id=target_channel_id,
            target_channel_handle=target_channel_handle,
            audience_state=audience_state,
            publication_authorized=publication_authorized,
            current_technical_readiness_state=current_technical_readiness,
            current_blocking_gate=current_blocking_gate,
            evidence_timestamp=evidence_timestamp,
            immutable_content_fingerprint=immutable_fingerprint,
            last_deterministic_verification_timestamp=verification_timestamp,
            source_files=sorted(list(set(source_files))),
            asset_state_hash=asset_state_hash,
        )
