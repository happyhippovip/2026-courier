#!/usr/bin/env python3
"""Mission PRODUCT-7 Real Work — FruitKI Inventory Summary Generator.

Generates authoritative runtime/content/inventory_summary.json from
runtime/content/catalog_manifest.json and runtime/content/qc_batch_report.json.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    temp_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


def generate_inventory_summary(repo_dir: Path = COURIER_DIR) -> dict[str, Any]:
    catalog_path = repo_dir / "runtime/content/catalog_manifest.json"
    qc_path = repo_dir / "runtime/content/qc_batch_report.json"

    if not catalog_path.is_file():
        raise FileNotFoundError("catalog_manifest.json not found")

    catalog = load_json(catalog_path)
    packages = catalog.get("packages", [])

    qc_report = load_json(qc_path) if qc_path.is_file() else {}
    qc_evals = {e["package_id"]: e for e in qc_report.get("evaluations", [])}

    total_packages = len(packages)
    rendered_shorts = []
    unrendered_packages = []
    qc_passed_packages = []
    qc_blocked_packages = []

    total_duration_seconds = 0.0
    theme_distribution: dict[str, int] = {}
    resolution_distribution: dict[str, int] = {}

    for pkg in packages:
        pkg_id = pkg["package_id"]
        media_files = pkg.get("media_files", [])
        has_video = any(m["filename"].endswith((".mp4", ".avi")) for m in media_files)

        theme = pkg.get("theme", "UNKNOWN")
        theme_distribution[theme] = theme_distribution.get(theme, 0) + 1

        dur = pkg.get("duration_seconds")
        if isinstance(dur, (int, float)) and dur > 0:
            total_duration_seconds += float(dur)

        res = pkg.get("resolution")
        if isinstance(res, dict) and "width" in res and "height" in res:
            res_key = f"{res['width']}x{res['height']}"
            resolution_distribution[res_key] = resolution_distribution.get(res_key, 0) + 1

        qc_eval = qc_evals.get(pkg_id, {})
        verdict = qc_eval.get("verdict", "UNKNOWN")

        if has_video:
            rendered_shorts.append(pkg_id)
            if verdict == "PASS":
                qc_passed_packages.append(pkg_id)
            elif verdict == "BLOCKED":
                qc_blocked_packages.append(pkg_id)
        else:
            unrendered_packages.append(pkg_id)

    summary = {
        "schema_version": "FRUITKI_INVENTORY_SUMMARY_V1",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_packages": total_packages,
        "rendered_video_packages_count": len(rendered_shorts),
        "unrendered_or_container_packages_count": len(unrendered_packages),
        "qc_passed_count": len(qc_passed_packages),
        "qc_blocked_count": len(qc_blocked_packages),
        "total_catalog_duration_seconds": round(total_duration_seconds, 2),
        "theme_distribution": theme_distribution,
        "resolution_distribution": resolution_distribution,
        "rendered_package_ids": sorted(rendered_shorts),
        "unrendered_package_ids": sorted(unrendered_packages),
        "qc_passed_package_ids": sorted(qc_passed_packages),
        "qc_blocked_package_ids": sorted(qc_blocked_packages),
        "ready_for_release_review_count": len(qc_passed_packages),
        "licensing_readiness": "READY" if len(qc_passed_packages) > 0 else "NOT_READY",
    }

    return summary


if __name__ == "__main__":
    res = generate_inventory_summary()
    out = COURIER_DIR / "runtime/content/inventory_summary.json"
    save_json_atomic(out, res)
    print("==================================================")
    print(f"INVENTORY SUMMARY GENERATED: {res['total_packages']} packages")
    print(f"  Rendered Videos: {res['rendered_video_packages_count']}")
    print(f"  QC PASS:         {res['qc_passed_count']}")
    print(f"  QC BLOCKED:      {res['qc_blocked_count']}")
    print(f"  Total Duration:  {res['total_catalog_duration_seconds']}s")
    print(f"Output: {out}")
    print("==================================================")
