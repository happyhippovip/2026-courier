"""
constitution.py - Windows Courier Operating Constitution Loader & Validator
Discovers, validates, and provides access to the canonical Operating Constitution.
"""

import os
import json
import hashlib
from typing import Dict, Any, Optional, Tuple

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CANONICAL_PATHS = [
    os.path.join(WORKSPACE_ROOT, "courier", "WINDOWS_COURIER_OPERATING_CONSTITUTION.json"),
    os.path.join(WORKSPACE_ROOT, "project-memory", "WINDOWS_COURIER_OPERATING_CONSTITUTION.json"),
    os.path.join(WORKSPACE_ROOT, "WINDOWS_COURIER_OPERATING_CONSTITUTION.json"),
]


class ConstitutionLoader:
    """Discovers and loads the authoritative Windows Courier Operating Constitution from disk."""

    @classmethod
    def discover_and_load(cls) -> Tuple[bool, Dict[str, Any], str, str]:
        for path in CANONICAL_PATHS:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        raw = f.read()
                    data = json.loads(raw)
                    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                    if data.get("status") == "ACTIVE" and "articles" in data:
                        return True, data, path, h
                except Exception:
                    continue
        return False, {}, "", ""

    @classmethod
    def get_summary(cls) -> Dict[str, Any]:
        success, data, path, h = cls.discover_and_load()
        if not success:
            return {"status": "NOT_FOUND"}
        return {
            "status": data.get("status"),
            "policy_version": data.get("policy_version"),
            "policy_path": path,
            "policy_hash": h,
            "machine_role": data.get("machine_role"),
            "canonical_authority": data.get("canonical_authority"),
            "article_count": len(data.get("articles", {}))
        }
