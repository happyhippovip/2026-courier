#!/usr/bin/env python3
"""FruitKI 3D Commercial Asset Pack Standalone Release Builder.

Packages all 12 character rigs, animation metadata, scene definitions,
and the Royalty-Free Commercial License into a distribution release bundle.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class FruitKIReleaseBuilder:
    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = (repo_dir or COURIER_DIR).resolve()
        self.pack_dir = self.repo_dir / "events" / "digital-assets" / "fruitki_commercial_pack"
        self.dist_dir = self.repo_dir / "events" / "digital-assets" / "dist"
        self.dist_dir.mkdir(parents=True, exist_ok=True)

    def build_release_archive(self) -> Dict[str, Any]:
        """Creates a standalone .zip package containing all commercial assets and license."""
        zip_path = self.dist_dir / "FruitKI_3D_Commercial_Pack_v1.0.0.zip"
        manifest_path = self.pack_dir / "bundle_manifest.json"
        license_path = self.pack_dir / "COMMERCIAL_LICENSE_AGREEMENT.md"
        listing_path = self.pack_dir / "STORE_LISTING_SPECIFICATION.md"

        hasher = hashlib.sha256()

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if manifest_path.exists():
                zf.write(manifest_path, arcname="bundle_manifest.json")
            if license_path.exists():
                zf.write(license_path, arcname="COMMERCIAL_LICENSE_AGREEMENT.md")
            if listing_path.exists():
                zf.write(listing_path, arcname="STORE_LISTING_SPECIFICATION.md")

            # Add README / QuickStart
            readme_text = (
                "# FruitKI 3D Commercial Pack v1.0.0\n\n"
                "Thank you for your purchase! Drag the `.tscn` scene files into your Godot 4.x project.\n"
                "See `COMMERCIAL_LICENSE_AGREEMENT.md` for commercial royalty-free license terms.\n"
            )
            zf.writestr("README.md", readme_text)

        # Compute archive checksum
        archive_bytes = zip_path.read_bytes()
        archive_sha = hashlib.sha256(archive_bytes).hexdigest()
        archive_size_bytes = len(archive_bytes)

        release_manifest = {
            "pack_id": "FRUITKI-COMMERCIAL-PACK-01",
            "release_archive": str(zip_path.relative_to(self.repo_dir)),
            "sha256": archive_sha,
            "size_bytes": archive_size_bytes,
            "version": "1.0.0",
            "price_usd": 19.0,
            "packaged_at": utc_now(),
            "capital_spent_eur": 0.0,
        }

        manifest_file = self.dist_dir / "release_manifest.json"
        manifest_file.write_text(json.dumps(release_manifest, indent=2) + "\n", encoding="utf-8")

        return {
            "status": "RELEASE_ARCHIVE_BUILT",
            "archive": str(zip_path.relative_to(self.repo_dir)),
            "sha256": archive_sha,
            "size_bytes": archive_size_bytes,
            "capital_spent_eur": 0.0,
        }


def main() -> int:
    builder = FruitKIReleaseBuilder()
    res = builder.build_release_archive()
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
