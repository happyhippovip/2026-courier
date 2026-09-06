#!/usr/bin/env python3
"""Discover only concrete, zero-cost Creator Factory stage gaps from local artifacts.

This module deliberately does not invent topics, customers, platform data, or
new media builds.  It promotes an item only when an existing local media master
has a deterministically missing next artifact.
"""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

try:
    from opportunity_queue import Opportunity
except ImportError:
    from scripts.opportunity_queue import Opportunity


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_creator_opportunities(repo_dir: Path) -> list[Opportunity]:
    """Return concrete QC/staging gaps for known locally authored FruitKI masters."""
    runtime = repo_dir / "runtime" / "content"
    source_root = Path("/Users/user/Downloads/2026-Projektzentrale/05-3D-Shorts-Produktion/godot-short-studio")
    candidates = (
        ("fruitki-golden-trophy", "golden_trophy_short", "render.mp4", "strawberry_golden_trophy.tscn"),
        ("fruitki-mystery-box", "mystery_box_short", "fruitki_strawberry_mystery_box.mp4", "strawberry_mystery_box.tscn"),
    )
    opportunities: list[Opportunity] = []
    for project_id, folder, media_name, scene_name in candidates:
        media = runtime / folder / media_name
        scene = source_root / scene_name
        if not media.is_file() or media.stat().st_size == 0 or not scene.is_file():
            continue
        source_hash = _sha256(media)
        qc_file = media.parent / "qc_report.json"
        package_file = media.parent / "publish_package.json"
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if not qc_file.exists():
            stage, action, goal, output = (
                "QC", "MEDIA_QC", "Validate existing local MP4 technical properties before any staging.", "qc_report.json"
            )
        else:
            # A package is only meaningful after a passing deterministic QC record.
            try:
                import json
                qc_passed = json.loads(qc_file.read_text(encoding="utf-8")).get("verdict") == "PASS"
            except Exception:
                qc_passed = False
            if not qc_passed or package_file.exists():
                continue
            stage, action, goal, output = (
                "READY_FOR_PUBLICATION", "PREPARE_PUBLICATION_PACKAGE",
                "Prepare a local, human-gated publication package for QC-passed media.", "publish_package.json"
            )
        fingerprint = hashlib.sha256(f"{project_id}:{stage}:{source_hash}".encode("utf-8")).hexdigest()
        opportunities.append(Opportunity(
            opportunity_id=f"OPP-CREATOR-{project_id.upper()}-{stage}",
            source="LOCAL_CREATOR_ARTIFACT",
            objective_id="PROCESS_APPROVED_CONTENT_QUEUE",
            project="2026-courier",
            project_id=project_id,
            source_artifact=str(media),
            source_hash=source_hash,
            evidence_type="LOCAL_MEDIA_AND_AUTHORED_SCENE",
            production_stage=stage,
            description=goal,
            problem_or_goal=goal,
            expected_output=output,
            expected_value="Persisted local Creator Factory evidence; no publication.",
            risk="LOW",
            risk_class="LOW",
            cost_class="ZERO_COST_LOCAL",
            required_capabilities=["FFPROBE", "LOCAL_JSON"],
            priority=10,
            allowed_scope=[str(media)],
            evidence={"creator_action": action, "scene": str(scene), "media": str(media)},
            dedupe_fingerprint=fingerprint,
            dedupe_hash=fingerprint[:16],
            target_agent="antigravity",
            heavy_job=True,
            created_at=created_at,
        ))
    return opportunities
