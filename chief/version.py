"""
version.py - Courier Symphony Windows Canonical Version & Build Metadata
"""

import os
import sys
import platform
import subprocess
from typing import Dict, Any

__version__ = "1.0.0-rc1"
PRODUCT_NAME = "Courier Symphony Windows"
RELEASE_TAG = "v1.0.0-rc1"
BUILD_DATE = "2026-09-13"
SCHEMA_VERSION = 1


def get_git_commit() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    # Fallback to RELEASE_MANIFEST if available
    manifest_path = os.path.join(os.path.dirname(__file__), "..", "RELEASE_MANIFEST.json")
    if os.path.exists(manifest_path):
        try:
            import json
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("git_commit", "unknown")
        except Exception:
            pass
    return "archive"


def get_version_info() -> Dict[str, Any]:
    from .constitution import ConstitutionLoader
    const_info = ConstitutionLoader.get_summary()

    return {
        "product_name": PRODUCT_NAME,
        "version": __version__,
        "release_tag": RELEASE_TAG,
        "build_date": BUILD_DATE,
        "schema_version": SCHEMA_VERSION,
        "git_commit": get_git_commit(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "constitution": const_info
    }
