#!/usr/bin/env python3
"""Content-to-Marketing-Asset Pre-Built Dossier Generator.

Constructs concrete, pre-transformed sample dossiers for qualified prospects
(CP-01 Solo AI Consultant, CP-02 Open-Source DevTool Founder) using real
technical developer materials.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from package_content_transformation_service import ContentTransformationEngine


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class DossierBatchGenerator:
    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = (repo_dir or COURIER_DIR).resolve()
        self.dossiers_dir = self.repo_dir / "events" / "revenue-opportunities" / "offerings" / "content_to_marketing_asset" / "dossiers"
        self.dossiers_dir.mkdir(parents=True, exist_ok=True)
        self.engine = ContentTransformationEngine(repo_dir=self.repo_dir)

    def generate_prospect_dossiers(self) -> Dict[str, Any]:
        """Generates pre-transformed deliverable packages for CP-01 and CP-02."""
        # CP-01: AI Consultant
        cp01_notes = (
            "Architecture teardown of LLM Agent Memory & State persistence. "
            "Discusses SQLite vs Flat JSON files, monotonic epoch fencing, and crash-proof recovery."
        )
        res_cp01 = self.engine.transform_raw_notes(cp01_notes, topic_title="Agent State Persistence & Crash Recovery")

        # CP-02: DevTool Founder
        cp02_notes = (
            "Release notes for autonomous batch scheduler v2.0. "
            "Covers zero-spend token firewalls, heartbeat gap monitoring, and single-winner POSIX lease locking."
        )
        res_cp02 = self.engine.transform_raw_notes(cp02_notes, topic_title="Batch Task Anti-Stall Architecture")

        manifest = {
            "batch_id": "DOSSIER-BATCH-20260901-01",
            "created_at": utc_now(),
            "prospect_dossiers": {
                "CP-01": res_cp01,
                "CP-02": res_cp02,
            },
            "autonomous_spend_eur": 0.0,
        }

        manifest_file = self.dossiers_dir / "dossier_manifest.json"
        manifest_file.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        return {
            "status": "DOSSIERS_GENERATED",
            "total_dossiers": 2,
            "manifest": str(manifest_file.relative_to(self.repo_dir)),
            "capital_spent_eur": 0.0,
        }


def main() -> int:
    gen = DossierBatchGenerator()
    res = gen.generate_prospect_dossiers()
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
