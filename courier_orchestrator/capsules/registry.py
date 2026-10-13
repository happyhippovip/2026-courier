"""Local capsule registry index (JSON, sha256-pinned) with quarantine, review, approval, recall."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schema import Capsule, CapsuleStatus
from .validate import validate_capsule


class RegistryError(Exception):
    pass


class CapsuleRegistry:
    def __init__(self, index_path: Path | str):
        self.path = Path(index_path)
        self.index: Dict[str, Any] = {"version": 1, "capsules": {}, "trust": {}}
        if self.path.exists():
            self.index = json.loads(self.path.read_text("utf-8"))

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.index, indent=2, sort_keys=True), "utf-8")
        tmp.replace(self.path)

    def _entry(self, key: str) -> Dict[str, Any]:
        if key not in self.index["capsules"]:
            raise RegistryError(f"unknown capsule {key}")
        return self.index["capsules"][key]

    # --- trust per author and task class ---
    def trust(self, author: str, task_class: str) -> int:
        return self.index["trust"].get(author, {}).get(task_class, 0)

    def _bump(self, author: str, task_class: str, delta: int) -> None:
        t = self.index["trust"].setdefault(author, {})
        t[task_class] = t.get(task_class, 0) + delta

    # --- lifecycle ---
    def upload(self, capsule: Capsule) -> Dict[str, Any]:
        res = validate_capsule(capsule)
        key = capsule.key
        if key in self.index["capsules"]:
            raise RegistryError(f"{key} already exists; bump version")
        entry = {"capsule": capsule.to_dict(), "sha256": capsule.sha256(),
                 "status": (CapsuleStatus.QUARANTINED if res.ok else CapsuleStatus.REJECTED).value,
                 "errors": res.errors, "reviews": [], "approved_by": None, "recall_reason": None}
        self.index["capsules"][key] = entry
        self._save()
        return entry

    def review(self, key: str, reviewer: str, passed: bool, note: str = "") -> None:
        e = self._entry(key)
        if e["status"] != CapsuleStatus.QUARANTINED.value:
            raise RegistryError("only quarantined capsules can be reviewed")
        if reviewer == e["capsule"]["author"]:
            raise RegistryError("review must be independent of the author")
        e["reviews"].append({"reviewer": reviewer, "passed": bool(passed), "note": note})
        self._save()

    def approve(self, key: str, human_approver: str) -> None:
        """Human gate: publish only after an independent passing review."""
        e = self._entry(key)
        if e["status"] != CapsuleStatus.QUARANTINED.value:
            raise RegistryError("only quarantined capsules can be approved")
        author = e["capsule"]["author"]
        if human_approver == author:
            raise RegistryError("author cannot approve own capsule")
        if not any(r["passed"] and r["reviewer"] != author for r in e["reviews"]):
            raise RegistryError("no independent passing review")
        if any(not r["passed"] for r in e["reviews"]):
            raise RegistryError("capsule has a failing review")
        if Capsule(**e["capsule"]).sha256() != e["sha256"]:
            raise RegistryError("sha256 mismatch")
        e["status"] = CapsuleStatus.APPROVED.value
        e["approved_by"] = human_approver
        self._bump(author, e["capsule"]["task_class"], +1)
        self._save()

    def recall(self, key: str, reason: str) -> None:
        e = self._entry(key)
        e["status"] = CapsuleStatus.RECALLED.value
        e["recall_reason"] = reason
        self._bump(e["capsule"]["author"], e["capsule"]["task_class"], -3)
        self._save()

    def status(self, key: str) -> CapsuleStatus:
        return CapsuleStatus(self._entry(key)["status"])

    def distribution_manifest(self) -> List[Dict[str, str]]:
        """What gets shipped to all users: approved, hash-verified capsules only. Recalls listed separately."""
        out = []
        for key, e in sorted(self.index["capsules"].items()):
            if e["status"] == CapsuleStatus.APPROVED.value and Capsule(**e["capsule"]).sha256() == e["sha256"]:
                out.append({"key": key, "sha256": e["sha256"]})
        return out

    def recalled_keys(self) -> List[str]:
        return sorted(k for k, e in self.index["capsules"].items() if e["status"] == CapsuleStatus.RECALLED.value)

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self.index["capsules"].get(key)
