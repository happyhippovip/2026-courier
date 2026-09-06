#!/usr/bin/env python3
"""Product-6C post-188G activation precheck and shadow-state pack; no runtime patch is applied here."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict


COURIER_DIR = Path(__file__).resolve().parent.parent
REQUIRED_MODULES = (
    "scripts/real_autonomy_runtime.py",
    "scripts/productivity_runtime_bridge.py",
    "scripts/parallel_dispatch_ready_pack.py",
    "scripts/completion_handoff_engine.py",
)


def _read(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _atomic_json(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="activation-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class EnduranceEvidenceReader:
    """Read-only normalization of 188G final evidence; never changes runtime/session data."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = Path(repo_dir)

    def read(self) -> Dict[str, Any]:
        runtime = self.repo_dir / "events" / "autonomy-runtime"
        heartbeat = _read(runtime / "heartbeat.json", {}) or {}
        final = _read(runtime / "endurance_final_acceptance.json", {}) or {}
        target = final.get("target_seconds", heartbeat.get("duration_target_hours", 8) * 3600)
        elapsed = final.get("elapsed_seconds", heartbeat.get("elapsed_seconds"))
        return {
            "session_id": final.get("session_id", heartbeat.get("session_id")),
            "status": final.get("status", heartbeat.get("status", "NOT_AVAILABLE")),
            "final_acceptance": final.get("final_acceptance", "MISSING"),
            "elapsed_seconds": elapsed,
            "target_seconds": target,
            "manual_interventions": final.get("manual_interventions"),
            "idle_model_calls": final.get("idle_model_calls"),
            "duplicate_work": final.get("duplicate_work"),
            "restart_recovery": final.get("restart_recovery"),
            "human_gate_isolation": final.get("human_gate_isolation"),
            "money_gate_isolation": final.get("money_gate_isolation"),
            "autonomous_spend": final.get("autonomous_spend"),
            "external_writes": final.get("external_writes"),
        }


class Post188GActivationPack:
    """One guarded activation switch. It refuses unless the final evidence is complete and clean."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = Path(repo_dir)
        self.state_path = self.repo_dir / "events" / "autonomy-runtime" / "parallel_runtime_v1.json"
        self.fingerprints = {name: self._hash(self.repo_dir / name) for name in REQUIRED_MODULES}

    @staticmethod
    def _hash(path: Path) -> str | None:
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return None

    def precheck(self) -> Dict[str, Any]:
        evidence = EnduranceEvidenceReader(self.repo_dir).read()
        blockers = []
        if evidence["status"] == "RUNNING":
            blockers.append("188G_STILL_RUNNING")
        if evidence["final_acceptance"] != "PASS":
            blockers.append("188G_FINAL_ACCEPTANCE_NOT_PASS")
        if not isinstance(evidence["elapsed_seconds"], (int, float)) or not isinstance(evidence["target_seconds"], (int, float)) or evidence["elapsed_seconds"] < evidence["target_seconds"]:
            blockers.append("188G_ELAPSED_PROOF_INSUFFICIENT")
        if evidence["autonomous_spend"] not in (0, 0.0):
            blockers.append("188G_SPEND_NOT_ZERO")
        if evidence["external_writes"] not in (0, 0.0, None):
            blockers.append("188G_EXTERNAL_WRITE_EVIDENCE")
        for name, expected in self.fingerprints.items():
            if not expected or self._hash(self.repo_dir / name) != expected:
                blockers.append(f"MODULE_FINGERPRINT_MISMATCH:{name}")
        return {"ready": not blockers, "blockers": blockers, "evidence": evidence, "activation_files": list(REQUIRED_MODULES)}

    def shadow_activate(self, acceptance_runner) -> Dict[str, Any]:
        """Atomic flag transition for isolated acceptance only; never edits executable runtime source."""
        check = self.precheck()
        if not check["ready"]:
            return {"activated": False, "precheck": check, "rollback": "NOT_NEEDED"}
        try:
            if not acceptance_runner():
                _atomic_json(self.state_path, {"PARALLEL_RUNTIME_V1": "OFF", "reason": "ACCEPTANCE_FAILED"})
                return {"activated": False, "precheck": check, "rollback": "COMPLETE"}
            _atomic_json(self.state_path, {"PARALLEL_RUNTIME_V1": "ON", "mode": "SHADOW_ACCEPTED"})
            return {"activated": True, "precheck": check, "rollback": "NOT_NEEDED"}
        except Exception as exc:
            _atomic_json(self.state_path, {"PARALLEL_RUNTIME_V1": "OFF", "reason": "ACTIVATION_EXCEPTION"})
            return {"activated": False, "precheck": check, "rollback": "COMPLETE", "error": type(exc).__name__}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--precheck", action="store_true")
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    pack = Post188GActivationPack()
    result = pack.precheck() if args.precheck or not args.activate else pack.shadow_activate(lambda: False)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ready", result.get("activated", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
