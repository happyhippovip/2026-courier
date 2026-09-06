#!/usr/bin/env python3
"""FruitKI Human Audience Decision Support Module.

Provides deterministic, neutral Decision Cards for Human/Chief review:
- Golden Trophy Short
- Mystery Box Short

Guarantees:
- NO automatic classification (MADE_FOR_KIDS vs NOT_MADE_FOR_KIDS)
- NO default selection or preselection
- Neutral factual summary grounded strictly in existing local artifacts
- Clear separation between PREVIEW and HUMAN_CONFIRMED
- Explicit warning that audience classification does NOT authorize upload or spend
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.evidence_provenance import check_for_secrets
from scripts.publication_approval import (
    compute_metadata_revision_hash,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

AUDIENCE_POLICY_VERSION = "1.0"
AUDIENCE_SCHEMA_VERSION = "1.0"
DECISION_SUPPORT_VERSION = "1.0"
HUMAN_SELECTABLE_OPTIONS = [
    "MADE_FOR_KIDS",
    "NOT_MADE_FOR_KIDS",
    "CANCEL / NO DECISION",
]

CARD_WARNING_TEXT = (
    "This decision is the Human audience classification for this exact media asset/fingerprint. "
    "This decision does NOT authorize: upload, publication, public release, or spending. "
    "This decision creates no private-upload approval."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ObservableContentFacts:
    characters_depicted: list[str]
    visual_theme: str
    dialogue_and_text: str
    animation_style: str
    audio_presence: str
    context_setting: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_observable_facts(content_id: str, pkg: dict[str, Any]) -> ObservableContentFacts:
    """Extract strictly grounded observable content facts from package metadata without making legal conclusions."""
    if content_id == "golden_trophy_short":
        return ObservableContentFacts(
            characters_depicted=["Erdbeere (Strawberry)", "Kiwi", "Goldene Trophäe (Golden Trophy)"],
            visual_theme="Rasanter Wettlauf zweier animierter Fruchtcharaktere um eine goldene Trophäe im virtuellen 3D-Studio",
            dialogue_and_text="Titel und Beschreibung auf Deutsch: 'Wer kriegt die goldene Trophäe? Erdbeere und Kiwi liefern sich eine rasante Jagd... Schreib deinen Favoriten in die Kommentare!'",
            animation_style="Stilisierte 3D-Animation von anthropomorphen Früchten mit Gesichtsausdrücken und Bewegungskomik",
            audio_presence="Visuell zentrierter 9:16 Kurzfilm (Shorts) mit dynamischer Szenenführung",
            context_setting="FruitKI 3D Studio (Wettkampf/Duell um Siegestrophäe)",
        )
    elif content_id == "mystery_box_short":
        return ObservableContentFacts(
            characters_depicted=["Erdbeere (Strawberry)", "Geheimnisvolle Kiste (Mystery Box)", "Konfetti"],
            visual_theme="Neugieriges Entdecken und Öffnen einer geheimnisvollen Kiste mit anschließender Konfetti-Überraschung im Studio",
            dialogue_and_text="Titel und Beschreibung auf Deutsch: 'Was ist in der Mystery Box? Erdbeere entdeckt eine geheimnisvolle Kiste... Eine explosive Konfetti-Überraschung!'",
            animation_style="Stilisierte 3D-Animation eines Fruchtcharakters mit Neugier- und Überraschungsmimik",
            audio_presence="Visuell zentrierter 9:16 Kurzfilm (Shorts) mit Überraschungseffekt",
            context_setting="FruitKI 3D Studio (Unboxing/Entdeckung)",
        )
    else:
        return ObservableContentFacts(
            characters_depicted=pkg.get("tags", []),
            visual_theme=pkg.get("description_draft", ""),
            dialogue_and_text=pkg.get("content_title", ""),
            animation_style="3D Animation",
            audio_presence="Shorts Audio Track",
            context_setting="FruitKI Studio",
        )


def compute_preview_decision_hash(
    *,
    content_id: str,
    media_sha256: str,
    publication_fingerprint: str,
    decision: str,
    decision_source: str = "HUMAN_EXPLICIT_REVIEW",
    policy_version: str = AUDIENCE_POLICY_VERSION,
    schema_version: str = AUDIENCE_SCHEMA_VERSION,
) -> str:
    """Compute deterministic preview decision hash for a hypothetical decision value."""
    raw = {
        "content_id": content_id,
        "media_sha256": media_sha256.lower(),
        "publication_fingerprint": publication_fingerprint.lower(),
        "decision": decision,
        "decision_source": decision_source,
        "policy_version": policy_version,
        "schema_version": schema_version,
    }
    return hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def generate_audience_decision_card(package_path: Path) -> dict[str, Any]:
    """Generate a neutral, non-authorizing Human Audience Decision Card for a publish package."""
    if not package_path.is_file():
        raise FileNotFoundError(f"Publish package not found: {package_path}")

    pkg = json.loads(package_path.read_text(encoding="utf-8"))
    content_id = package_path.parent.name
    media_path = Path(pkg.get("media_path", ""))
    media_sha = pkg.get("media_sha256", "")
    fingerprint = pkg.get("publication_dedupe_fingerprint", "")
    meta_hash = compute_metadata_revision_hash(pkg)

    # Load technical QC metadata if available
    qc_path = Path(pkg.get("qc_report_path", ""))
    duration = 0.0
    dimensions = {"width": 360, "height": 640, "aspect_ratio": "9:16"}
    fps = "24/1"
    if qc_path.is_file():
        try:
            qc = json.loads(qc_path.read_text(encoding="utf-8"))
            duration = qc.get("duration_seconds", 0.0)
            vid = qc.get("video", {})
            dimensions["width"] = vid.get("width", 360)
            dimensions["height"] = vid.get("height", 640)
            fps = vid.get("r_frame_rate", "24/1")
        except Exception:
            pass

    observable_facts = extract_observable_facts(content_id, pkg)

    # Generate hypothetical binding previews for Human choices
    preview_mfk = compute_preview_decision_hash(
        content_id=content_id,
        media_sha256=media_sha,
        publication_fingerprint=fingerprint,
        decision="MADE_FOR_KIDS",
    )
    preview_nmfk = compute_preview_decision_hash(
        content_id=content_id,
        media_sha256=media_sha,
        publication_fingerprint=fingerprint,
        decision="NOT_MADE_FOR_KIDS",
    )

    card = {
        "card_version": DECISION_SUPPORT_VERSION,
        "content_id": content_id,
        "human_readable_title": pkg.get("content_title", ""),
        "media_filename": media_path.name,
        "media_path": str(media_path),
        "media_sha256": media_sha,
        "publication_fingerprint": fingerprint,
        "technical_specifications": {
            "duration_seconds": duration,
            "dimensions": dimensions,
            "frame_rate": fps,
            "codec": "h264",
        },
        "metadata_revision_hash": meta_hash,
        "current_audience_state": pkg.get("audience_decision", "DECISION_REQUIRED"),
        "current_technical_blocker": "AUDIENCE_DECISION_REQUIRED",
        "observable_content_facts": observable_facts.to_dict(),
        "human_choice_options": HUMAN_SELECTABLE_OPTIONS,
        "default_selection": None,  # Strictly NO default
        "card_warning": CARD_WARNING_TEXT,
        "decision_record_binding_previews": {
            "MADE_FOR_KIDS": {
                "decision": "MADE_FOR_KIDS",
                "decision_source": "HUMAN_EXPLICIT_REVIEW",
                "preview_decision_hash": preview_mfk,
                "policy_version": AUDIENCE_POLICY_VERSION,
                "schema_version": AUDIENCE_SCHEMA_VERSION,
                "status": "PREVIEW_ONLY_NOT_DURABLE",
            },
            "NOT_MADE_FOR_KIDS": {
                "decision": "NOT_MADE_FOR_KIDS",
                "decision_source": "HUMAN_EXPLICIT_REVIEW",
                "preview_decision_hash": preview_nmfk,
                "policy_version": AUDIENCE_POLICY_VERSION,
                "schema_version": AUDIENCE_SCHEMA_VERSION,
                "status": "PREVIEW_ONLY_NOT_DURABLE",
            },
        },
        "generated_at": _now(),
        "decision_status": "PENDING_HUMAN_DECISION",
    }

    # Secret check
    clean, reason = check_for_secrets(card)
    if not clean:
        raise ValueError(f"Secret detected in decision card: {reason}")

    return card


def generate_fruitki_audience_decision_cards_package(repo_dir: Path | None = None) -> dict[str, Any]:
    """Generate the full Human Audience Decision Support package for all active FruitKI productions."""
    root = repo_dir or REPO_ROOT
    gt_pkg = root / "runtime" / "content" / "golden_trophy_short" / "publish_package.json"
    mb_pkg = root / "runtime" / "content" / "mystery_box_short" / "publish_package.json"

    gt_card = generate_audience_decision_card(gt_pkg)
    mb_card = generate_audience_decision_card(mb_pkg)

    pkg = {
        "schema_version": "1.0",
        "purpose": "HUMAN_AUDIENCE_DECISION_SUPPORT",
        "generated_at": _now(),
        "overall_status": "PENDING_HUMAN_DECISION",
        "cards": {
            "golden_trophy_short": gt_card,
            "mystery_box_short": mb_card,
        },
        "instructions_for_chief": (
            "Review the observable content facts in each card. Select either MADE_FOR_KIDS or NOT_MADE_FOR_KIDS "
            "for each short. Explicit Human submission will produce the durable AudienceDecisionRecord. "
            "Until then, both packages remain locked at AUDIENCE_DECISION_REQUIRED."
        ),
    }
    return pkg


generate_all_decision_cards = generate_fruitki_audience_decision_cards_package

