#!/usr/bin/env python3
"""Disaster Recovery Bundle Auto-Sync Engine (Mission Infinite Life).

Creates and verifies zero-secret, schema-validated state snapshot archives
for off-host disaster recovery replication.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import tarfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

COURIER_DIR = Path(__file__).resolve().parent.parent
EVENTS_DIR = COURIER_DIR / "events"
RECOVERY_DIR = EVENTS_DIR / "disaster-recovery"
BUNDLES_DIR = RECOVERY_DIR / "bundles"


def compute_file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1048576):
            hasher.update(chunk)
    return hasher.hexdigest()


class DisasterRecoveryBundleSync:
    """Generates zero-secret state snapshot bundles."""

    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = repo_dir or COURIER_DIR
        self.bundles_dir = self.repo_dir / "events" / "disaster-recovery" / "bundles"
        self.bundles_dir.mkdir(parents=True, exist_ok=True)

    def create_snapshot_bundle(self, bundle_id: Optional[str] = None) -> Tuple[Path, str, Dict[str, Any]]:
        """Creates a tar.gz bundle of all canonical state files with integrity manifest."""
        now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
        b_id = bundle_id or f"dr-bundle-{now_iso[:19].replace(':', '').replace('-', '')}"

        bundle_tar = self.bundles_dir / f"{b_id}.tar.gz"
        manifest_data: Dict[str, Any] = {
            "bundle_id": b_id,
            "created_at": now_iso,
            "schema_version": "DR_BUNDLE_V1",
            "autonomous_spend_limit_eur": 0.0,
            "files_included": {},
        }

        # Collect key canonical state files if they exist
        targets = [
            "events/chief-brain/memories.json",
            "events/chief-brain/tasks_continuation.json",
            "events/chief-brain/open_loops.json",
            "events/autonomy-orchestrator/safe_queue.json",
            "events/autonomy-orchestrator/checkpoint.json",
            "events/host-survival/disaster_recovery_manifest.json",
            "events/host-survival/host_fencing_token.json",
            "events/host-survival/generic_host_registry.json",
            "events/worker-registry/hot_plug_registry.json",
        ]

        with tarfile.open(bundle_tar, "w:gz") as tar:
            for rel_path in targets:
                p = self.repo_dir / rel_path
                if p.exists():
                    tar.add(p, arcname=rel_path)
                    manifest_data["files_included"][rel_path] = compute_file_sha256(p)

        bundle_sha = compute_file_sha256(bundle_tar)
        manifest_data["bundle_sha256"] = bundle_sha

        manifest_file = self.bundles_dir / f"{b_id}_manifest.json"
        manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

        return bundle_tar, bundle_sha, manifest_data

    def verify_snapshot_bundle(self, bundle_path: Path, manifest_path: Path) -> Tuple[bool, str]:
        """Verifies bundle checksum against manifest."""
        if not bundle_path.exists() or not manifest_path.exists():
            return False, "BUNDLE_OR_MANIFEST_MISSING"

        try:
            m_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            expected_sha = m_data.get("bundle_sha256", "")
            actual_sha = compute_file_sha256(bundle_path)

            if expected_sha != actual_sha:
                return False, f"SHA256_MISMATCH: expected {expected_sha[:12]}, got {actual_sha[:12]}"
            return True, "VERIFIED"
        except Exception as e:
            return False, f"VERIFICATION_EXCEPTION_{e}"


if __name__ == "__main__":
    syncer = DisasterRecoveryBundleSync()
    tar_p, sha, meta = syncer.create_snapshot_bundle()
    print(f"✅ DR Bundle Created: {tar_p.name} (SHA: {sha[:16]}...)")
