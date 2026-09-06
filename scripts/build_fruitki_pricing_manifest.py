#!/usr/bin/env python3
"""Mission PRODUCT-7 Real Work — FruitKI Licensing Tiers & Pricing Manifest Builder.

Constructs authoritative revenue-path asset licensing tier structure and
pricing metadata specification in runtime/content/licensing_tiers.json.
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


def generate_pricing_manifest(repo_dir: Path = COURIER_DIR) -> dict[str, Any]:
    catalog_path = repo_dir / "runtime/content/catalog_manifest.json"
    inv_path = repo_dir / "runtime/content/inventory_summary.json"

    if not catalog_path.is_file():
        raise FileNotFoundError("catalog_manifest.json not found")

    catalog = load_json(catalog_path)
    inv = load_json(inv_path) if inv_path.is_file() else {}
    qc_passed_ids = set(inv.get("qc_passed_package_ids", []))

    packages = catalog.get("packages", [])

    # Canonical licensing tiers definition
    licensing_tiers = [
        {
            "tier_id": "TIER_FREE_PREVIEW",
            "name": "Free Preview License",
            "base_price_eur": 0.00,
            "commercial_use_allowed": False,
            "derivative_works_allowed": False,
            "platforms": ["YOUTUBE", "TIKTOK", "INSTAGRAM_REELS"],
            "description": "Non-commercial reference and preview access with attribution requirement.",
        },
        {
            "tier_id": "TIER_STANDARD_COMMERCIAL",
            "name": "Standard Creator License",
            "base_price_eur": 19.99,
            "commercial_use_allowed": True,
            "derivative_works_allowed": True,
            "platforms": ["YOUTUBE", "TIKTOK", "INSTAGRAM_REELS"],
            "description": "Single channel commercial publishing rights with monetization enabled.",
        },
        {
            "tier_id": "TIER_EXTENDED_COMMERCIAL",
            "name": "Extended Network License",
            "base_price_eur": 79.99,
            "commercial_use_allowed": True,
            "derivative_works_allowed": True,
            "platforms": ["ALL_DIGITAL_PLATFORMS"],
            "description": "Multi-channel broadcast, paid social ads, and syndication rights.",
        },
        {
            "tier_id": "TIER_EXCLUSIVE_BUYOUT",
            "name": "Exclusive Master Rights Buyout",
            "base_price_eur": 299.99,
            "commercial_use_allowed": True,
            "derivative_works_allowed": True,
            "platforms": ["UNRESTRICTED_GLOBAL"],
            "description": "Complete master ownership transfer, source assets, and full copyright assignment.",
        },
    ]

    package_licensing = []
    for pkg in packages:
        pkg_id = pkg["package_id"]
        is_qc_pass = pkg_id in qc_passed_ids or pkg.get("qc_status") == "PASS"
        dur = pkg.get("duration_seconds", 0.0)

        package_licensing.append({
            "package_id": pkg_id,
            "content_id": pkg.get("content_id", pkg_id),
            "theme": pkg.get("theme", "UNKNOWN"),
            "duration_seconds": dur,
            "qc_verified": is_qc_pass,
            "licensing_eligibility": "ELIGIBLE" if is_qc_pass else "BLOCKED_QC_REQUIRED",
            "supported_tiers": ["TIER_FREE_PREVIEW", "TIER_STANDARD_COMMERCIAL", "TIER_EXTENDED_COMMERCIAL", "TIER_EXCLUSIVE_BUYOUT"] if is_qc_pass else ["TIER_FREE_PREVIEW"],
        })

    manifest = {
        "schema_version": "FRUITKI_LICENSING_TIERS_V1",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_tiers_defined": len(licensing_tiers),
        "total_packages_mapped": len(package_licensing),
        "eligible_commercial_packages_count": sum(1 for p in package_licensing if p["licensing_eligibility"] == "ELIGIBLE"),
        "currency": "EUR",
        "tiers": licensing_tiers,
        "packages": package_licensing,
    }

    return manifest


if __name__ == "__main__":
    res = generate_pricing_manifest()
    out = COURIER_DIR / "runtime/content/licensing_tiers.json"
    save_json_atomic(out, res)
    print("==================================================")
    print(f"LICENSING MANIFEST GENERATED: {res['total_tiers_defined']} tiers, {res['total_packages_mapped']} packages")
    print(f"  Eligible Commercial Packages: {res['eligible_commercial_packages_count']}")
    print(f"Output: {out}")
    print("==================================================")
