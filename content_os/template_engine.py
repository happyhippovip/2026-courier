"""
Revenue-First Content OS — Deterministic Script & Asset Manifest Engine
Generates structured 4-phase short-form scripts and asset plans for Shorts/TikTok.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class ScriptPhase:
    phase_name: str
    timing_sec: str
    spoken_text: str
    visual_cue: str
    on_screen_text: str


@dataclass
class AssetManifest:
    aspect_ratio: str  # e.g. "9:16" or "16:9"
    target_duration_sec: int
    required_cards: List[str]
    audio_spec: str
    thumbnail_concept: str


@dataclass
class ContentPackage:
    video_id: str
    lane_id: str
    channel_name: str
    title: str
    description: str
    tags: List[str]
    script_phases: List[ScriptPhase]
    asset_manifest: AssetManifest
    affiliate_links: List[str]

    def formatted_script(self) -> str:
        lines = [
            f"=== SCRIPT FOR: {self.title} ===",
            f"CHANNEL: {self.channel_name} ({self.lane_id})",
            f"DURATION: ~{self.asset_manifest.target_duration_sec}s | RATIO: {self.asset_manifest.aspect_ratio}",
            ""
        ]
        for p in self.script_phases:
            lines.append(f"[{p.phase_name.upper()} | {p.timing_sec}]")
            lines.append(f"VOICE: \"{p.spoken_text}\"")
            lines.append(f"VISUAL: {p.visual_cue}")
            lines.append(f"ON-SCREEN: {p.on_screen_text}")
            lines.append("")
        return "\n".join(lines)


class ShortFormTemplateEngine:
    """
    Deterministic template engine for generating high-retention 30-60s scripts.
    Ensures zero rambling, strict pacing, and clear monetization hooks.
    """

    @staticmethod
    def generate_short_package(
        video_id: str,
        lane_id: str,
        channel_name: str,
        title: str,
        hook_text: str,
        problem_text: str,
        solution_points: List[str],
        cta_text: str,
        tags: List[str],
        affiliate_links: List[str]
    ) -> ContentPackage:
        phases = [
            ScriptPhase(
                phase_name="Hook",
                timing_sec="0-3s",
                spoken_text=hook_text,
                visual_cue="Rapid kinetic text punch + dynamic zoom on key metric/word",
                on_screen_text=hook_text[:40].upper()
            ),
            ScriptPhase(
                phase_name="Problem / Stakes",
                timing_sec="3-10s",
                spoken_text=problem_text,
                visual_cue="Highlighting the friction/cost/mistake with contrasting red highlight",
                on_screen_text="THE HIDDEN COST"
            ),
            ScriptPhase(
                phase_name="Core Value / Solution",
                timing_sec="10-45s",
                spoken_text=" ".join(solution_points),
                visual_cue="Step-by-step graphic cards showing proof, numbers, and workflow",
                on_screen_text="STEP-BY-STEP BREAKDOWN"
            ),
            ScriptPhase(
                phase_name="Call To Action",
                timing_sec="45-60s",
                spoken_text=cta_text,
                visual_cue="Clean outro card with channel handle and link arrow",
                on_screen_text="LINK IN BIO / COMMENTS"
            )
        ]

        manifest = AssetManifest(
            aspect_ratio="9:16",
            target_duration_sec=55,
            required_cards=["hook_card_01.png", "problem_card_02.png", "solution_card_03.png", "cta_card_04.png"],
            audio_spec="Clear 1.1x speed neutral narration, subtle low-frequency background tech beat (-22dB)",
            thumbnail_concept="High-contrast 9:16 frame featuring bold 3-word title overlay and key stat"
        )

        description = (
            f"{title}\n\n"
            f"Resources & Links:\n" + "\n".join(f"👉 {link}" for link in affiliate_links) + "\n\n"
            f"Follow for more daily {channel_name} breakdowns.\n"
            f"#{' #'.join(tags)}"
        )

        return ContentPackage(
            video_id=video_id,
            lane_id=lane_id,
            channel_name=channel_name,
            title=title,
            description=description,
            tags=tags,
            script_phases=phases,
            asset_manifest=manifest,
            affiliate_links=affiliate_links
        )
