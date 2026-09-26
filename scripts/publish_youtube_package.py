#!/usr/bin/env python3
"""
Offline-ready Publisher for YouTube Content Packages.
This reads the manifest from a READY_TO_PUBLISH stage,
validates credentials, and uses the YouTubeProvider for safe, idempotent publishing.
"""

import argparse
import json
import os
import logging
from pathlib import Path

# Adjust import path to include providers
import sys
sys.path.append(str(Path(__file__).parent.parent))

from providers.youtube_provider import YouTubeProvider, MissingCredentialError

def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def publish_package(manifest_path, dry_run=True):
    logger = logging.getLogger("YouTubePublisher")

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    stages = manifest.get("stages", {})
    if "READY_TO_PUBLISH" not in stages or stages["READY_TO_PUBLISH"].get("status") != "COMPLETED":
        logger.error("Package is not READY_TO_PUBLISH.")
        return False

    pkg_details = stages["READY_TO_PUBLISH"].get("details", {})
    metadata = pkg_details.get("metadata", {})

    if not metadata:
        logger.error("No metadata found in package.")
        return False

    # The artifact_path from the VIDEO_BUILD stage is usually what we want
    video_artifact = None
    for art in manifest.get("artifacts", []):
        if art.get("stage") in ["VIDEO_BUILD", "VERTICAL_VIDEO_BUILD"]:
            video_artifact = art.get("relative_path")
            break

    if not video_artifact:
        logger.error("No built video artifact found in manifest.")
        return False

    mission_dir = Path(manifest_path).parent
    video_abs_path = str((mission_dir / video_artifact).resolve())

    payload = {
        "title": metadata.get("title", ""),
        "description": metadata.get("description", ""),
        "tags": metadata.get("tags", []),
        "privacy_status": metadata.get("privacy_status", "private"),
        "video_path": video_abs_path
    }

    idempotency_key = f"yt_{manifest.get('mission_id', 'unknown')}_{manifest.get('workflow_id', 'unknown')}"

    try:
        provider = YouTubeProvider(dry_run=dry_run)
    except MissingCredentialError as e:
        logger.error(f"FAIL-CLOSED: Credentials absent. {e}")
        return False

    logger.info(f"Initiating publish for {idempotency_key} (dry_run={dry_run})")

    try:
        receipt = provider.upload_video(payload, idempotency_key=idempotency_key)
        logger.info(f"Publish result: {receipt}")
        return True
    except ValueError as e:
        logger.error(f"Payload Validation Error: {e}")
        return False
    except MissingCredentialError as e:
        logger.error(f"FAIL-CLOSED: Credentials absent at upload. {e}")
        return False

if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, help="Path to pipeline manifest.json")
    parser.add_argument("--live", action="store_true", help="Execute real upload instead of dry-run")
    args = parser.parse_args()

    success = publish_package(args.manifest, dry_run=not args.live)
    if not success:
        sys.exit(1)
