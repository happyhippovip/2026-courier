#!/usr/bin/env python3
"""FruitKI / Creator Factory Asset Catalog Manifest Builder.

Deterministic scanner and catalog generator for all existing real packages
in runtime/content/.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent


def load_json_safe(path: Optional[Path], default: Any = None) -> Any:
    if not path or not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1048576):  # 1MB chunks
            h.update(chunk)
    return h.hexdigest()


def build_catalog_manifest(repo_dir: Path = COURIER_DIR) -> dict[str, Any]:
    content_dir = repo_dir / "runtime/content"
    if not content_dir.exists():
        raise FileNotFoundError(f"Content directory {content_dir} does not exist")

    packages: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()

    for d in sorted(content_dir.iterdir()):
        if not d.is_dir():
            continue

        pkg_name = d.name
        if pkg_name in seen_ids:
            continue
        seen_ids.add(pkg_name)

        # Inspect local files in package directory
        local_files = {}
        for item in d.iterdir():
            if item.is_file():
                local_files[item.name] = item

        # Read JSON metadata files if present
        pub_pkg = load_json_safe(local_files.get("publish_package.json"))
        qc_rep = load_json_safe(local_files.get("qc_report.json"))
        rend_meta = load_json_safe(local_files.get("render_metadata.json"))

        # Pre-cached hashes from canonical metadata
        canonical_hashes = {}
        if pub_pkg and isinstance(pub_pkg, dict) and pub_pkg.get("master_sha256"):
            master_name = Path(pub_pkg.get("master_path", "")).name
            if master_name:
                canonical_hashes[master_name] = pub_pkg["master_sha256"]
        if qc_rep and isinstance(qc_rep, dict) and qc_rep.get("source_hash"):
            media_name = Path(qc_rep.get("media", "")).name
            if media_name:
                canonical_hashes[media_name] = qc_rep["source_hash"]

        # Discover real media files in package directory
        media_assets = []
        for fname, fpath in sorted(local_files.items()):
            ext = fpath.suffix.lower()
            if ext in (".mp4", ".avi", ".mov", ".webm", ".png"):
                rel_path = str(fpath.relative_to(repo_dir))
                if rel_path in seen_paths:
                    continue
                seen_paths.add(rel_path)

                sha = canonical_hashes.get(fname)
                if not sha:
                    sha = compute_file_sha256(fpath)

                size_bytes = fpath.stat().st_size
                media_assets.append({
                    "filename": fname,
                    "relative_path": rel_path,
                    "sha256": sha,
                    "size_bytes": size_bytes,
                    "extension": ext[1:],
                })

        # Extract deterministic video/audio metadata
        duration_sec = "NOT_AVAILABLE"
        resolution = "NOT_AVAILABLE"
        fps = "NOT_AVAILABLE"
        video_codec = "NOT_AVAILABLE"
        audio_info = "NOT_AVAILABLE"

        if qc_rep and isinstance(qc_rep, dict):
            if "duration_seconds" in qc_rep:
                duration_sec = qc_rep["duration_seconds"]
            v_info = qc_rep.get("video", {})
            if isinstance(v_info, dict):
                video_codec = v_info.get("codec_name", "NOT_AVAILABLE")
                if "width" in v_info and "height" in v_info:
                    resolution = {"width": v_info["width"], "height": v_info["height"]}
                if "fps" in v_info:
                    fps = v_info["fps"]
            a_info = qc_rep.get("audio")
            if isinstance(a_info, dict):
                audio_info = {
                    "codec_name": a_info.get("codec_name", "NOT_AVAILABLE"),
                    "channels": a_info.get("channels", "NOT_AVAILABLE"),
                    "sample_rate": a_info.get("sample_rate", "NOT_AVAILABLE"),
                }
            elif a_info is None:
                audio_info = "NONE"

        if rend_meta and isinstance(rend_meta, dict):
            if duration_sec == "NOT_AVAILABLE" and "duration_seconds" in rend_meta:
                duration_sec = rend_meta["duration_seconds"]
            if fps == "NOT_AVAILABLE" and "fps" in rend_meta:
                fps = rend_meta["fps"]
            probe = rend_meta.get("mp4_probe", {})
            if isinstance(probe, dict):
                if video_codec == "NOT_AVAILABLE" and "codec_name" in probe:
                    video_codec = probe["codec_name"]
                if resolution == "NOT_AVAILABLE" and "width" in probe and "height" in probe:
                    resolution = {"width": probe["width"], "height": probe["height"]}

        # Extract QC verdict and publication status
        qc_verdict = "NOT_AVAILABLE"
        if qc_rep and isinstance(qc_rep, dict):
            qc_verdict = qc_rep.get("verdict", qc_rep.get("status", "NOT_AVAILABLE"))

        product_family = "FruitKI"
        title = "NOT_AVAILABLE"
        description = "NOT_AVAILABLE"
        platforms = "NOT_AVAILABLE"
        pub_auth = False

        if pub_pkg and isinstance(pub_pkg, dict):
            product_family = pub_pkg.get("product_family", "FruitKI")
            title = pub_pkg.get("title", "NOT_AVAILABLE")
            description = pub_pkg.get("description", "NOT_AVAILABLE")
            platforms = pub_pkg.get("platforms", "NOT_AVAILABLE")
            pub_auth = pub_pkg.get("publication_authorized", False)

        entry = {
            "package_id": pkg_name,
            "content_id": pub_pkg.get("content_id", pkg_name) if pub_pkg else pkg_name,
            "title": title,
            "product_family": product_family,
            "relative_directory": f"runtime/content/{pkg_name}",
            "media_files": media_assets,
            "media_count": len(media_assets),
            "has_render_master": any(m["filename"].endswith((".mp4", ".avi")) for m in media_assets),
            "duration_seconds": duration_sec,
            "resolution": resolution,
            "fps": fps,
            "video_codec": video_codec,
            "audio_info": audio_info,
            "qc_status": qc_verdict,
            "publication_authorized": pub_auth,
            "platforms": platforms,
            "metadata_files_present": sorted(list(local_files.keys())),
        }
        packages.append(entry)

    catalog = {
        "schema_version": "CATALOG_MANIFEST_V1",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_packages": len(packages),
        "packages_with_media": sum(1 for p in packages if p["media_count"] > 0),
        "packages_qc_passed": sum(1 for p in packages if p["qc_status"] == "PASS"),
        "packages": packages,
    }
    return catalog


def validate_catalog_manifest(catalog: dict[str, Any], repo_dir: Path = COURIER_DIR) -> tuple[bool, list[str]]:
    """Validates catalog integrity against real filesystem evidence."""
    errors = []
    seen_ids = set()
    seen_paths = set()

    for pkg in catalog.get("packages", []):
        pid = pkg.get("package_id")
        if not pid:
            errors.append("Missing package_id in entry")
            continue
        if pid in seen_ids:
            errors.append(f"Duplicate package_id: {pid}")
        seen_ids.add(pid)

        pkg_dir = repo_dir / pkg.get("relative_directory", "")
        if not pkg_dir.is_dir():
            errors.append(f"Package directory does not exist: {pkg_dir}")

        for m in pkg.get("media_files", []):
            m_path = repo_dir / m.get("relative_path", "")
            if not m_path.is_file():
                errors.append(f"Referenced media file does not exist: {m_path}")
            if m["relative_path"] in seen_paths:
                errors.append(f"Duplicate media path across packages: {m['relative_path']}")
            seen_paths.add(m["relative_path"])

    return len(errors) == 0, errors


if __name__ == "__main__":
    cat = build_catalog_manifest()
    out_path = COURIER_DIR / "runtime/content/catalog_manifest.json"
    out_path.write_text(json.dumps(cat, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Catalog manifest written to {out_path} ({cat['total_packages']} packages)")

    is_valid, errs = validate_catalog_manifest(cat)
    if is_valid:
        print("DETERMINISTIC VALIDATION: PASS")
    else:
        print("DETERMINISTIC VALIDATION: FAIL")
        for e in errs:
            print(f"  ERROR: {e}")
        sys.exit(1)
