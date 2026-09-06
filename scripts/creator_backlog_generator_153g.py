#!/usr/bin/env python3
"""Creator Factory Backlog Specification Generator (Mission 153G).

Expands the 15 seed concepts into fully structured, production-ready video package specifications
for autonomous rendering and human audience review.

Adheres strictly to:
- 720x1280 (9:16 vertical short format)
- 8.0s duration (240 frames @ 30fps)
- 3-act short formula: Hook (0-2s) -> Escalation (2-6s) -> Climax/Loop (6-8s)
- Audio brief with stem synthesis parameters
- Zero external spend (AUTONOMOUS_SPEND_LIMIT = 0 EUR)
- PUBLICATION_AUTHORIZATION = DENY (Decision required by Chief)
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List

COURIER_DIR = Path(__file__).resolve().parent.parent
RUNTIME_CONTENT_DIR = COURIER_DIR / "runtime" / "content"
BACKLOG_SPECS_FILE = RUNTIME_CONTENT_DIR / "mission_153g_creator_backlog_specs.json"

SEEDS = [
    {"slug": "dragonfruit_fire_breath_short", "title": "Drachenfrucht Feuer-Atem Challenge", "concept": "Drachenfrucht isst Chilisauce und spuckt bunte Konfetti-Flammen.", "hook": "Rauchende Drachenfrucht vor brennendem Vulkan.", "mechanic": "COMEDY_TRANSFORMATION", "difficulty": "MEDIUM"},
    {"slug": "magnetic_fruit_chaos_short", "title": "Das magnetische Früchte-Chaos", "concept": "Riesen-Magnet zieht alle Beeren an den Kühlschrank.", "hook": "Metall-Löffel fliegt magnetisch auf Melone zu.", "mechanic": "MAGNETIC_PHYSICS", "difficulty": "LOW"},
    {"slug": "strawberry_snowboard_slalom_short", "title": "Erdbeere Snowboard-Slalom", "concept": "Erdbeere carvt im Tiefschnee um riesige Eiszapfen.", "hook": "Steiler Bergabhang mit Pulverschnee-Gischt.", "mechanic": "SPEED_SPORT", "difficulty": "MEDIUM"},
    {"slug": "coconut_bowling_strike_short", "title": "Kokosnuss Bowling-Strike", "concept": "Kokosnuss rollt über polierte Bahn und räumt 10 Ananas-Pins ab.", "hook": "Kokosnuss visiert leuchtende Pins an.", "mechanic": "BOWLING_IMPACT", "difficulty": "LOW"},
    {"slug": "invisible_fruit_prank_short", "title": "Der Unsichtbarkeits-Frucht-Streich", "concept": "Kiwi malt sich mit Tarnfarbe an und erschreckt Banane.", "hook": "Schwebender Apfel ohne sichtbaren Träger.", "mechanic": "MYSTERY_PRANK", "difficulty": "MEDIUM"},
    {"slug": "fruit_pinball_arcade_short", "title": "Frucht-Flipper-Automat Abenteuer", "concept": "Blaubeere wird von Bumpern durch Neon-Flipper geschossen.", "hook": "Blinkende Flipper-Rampe mit 1 Million Punkten.", "mechanic": "ARCADE_PHYSICS", "difficulty": "HIGH"},
    {"slug": "popcorn_cannon_surprise_short", "title": "Die Popcorn-Kanonen-Überraschung", "concept": "Maiskolben springt ins heiße Öl und poppt als Riesen-Popcorn heraus.", "hook": "Glühende Pfanne mit zitterndem Maiskorn.", "mechanic": "TRANSFORMATION_REACTION", "difficulty": "MEDIUM"},
    {"slug": "banana_clone_army_short", "title": "Bananen Klon-Armee", "concept": "Kopierer vervielfacht Banane in 50 tanzende Minis.", "hook": "Kopierer spuckt endlose Reihen von Bananen aus.", "mechanic": "CHAOS_MULTIPLICATION", "difficulty": "HIGH"},
    {"slug": "fruit_tower_jenga_short", "title": "Frucht-Turm Jenga Nervenkitzel", "concept": "Zitrone zieht den untersten Holzblock heraus.", "hook": "Wackelnder 2-Meter-Turm aus Früchten.", "mechanic": "SUSPENSE_BALANCE", "difficulty": "LOW"},
    {"slug": "paintball_fruit_battle_short", "title": "Bunte Paintball-Fruchtschlacht", "concept": "Erdbeere und Kiwi bewerfen sich mit bunten Fruchtfarben.", "hook": "Farbklecks trifft Kameralinse.", "mechanic": "COLORFUL_BATTLE", "difficulty": "MEDIUM"},
    {"slug": "submarine_blueberry_deep_dive_short", "title": "U-Boot Blaubeere Tiefsee-Tauchgang", "concept": "Blaubeere taucht im Glas-U-Boot zu glühenden Quallen.", "hook": "Dunkles Meer mit biolumineszentem Leuchten.", "mechanic": "UNDERWATER_EXPLORE", "difficulty": "HIGH"},
    {"slug": "watermelon_sumo_showdown_short", "title": "Melonen Sumo-Ringer Finale", "concept": "Zwei Riesenmelonen prallen im Sandring aufeinander.", "hook": "Sumo-Stampfen vor staubiger Arena.", "mechanic": "SPORTS_COMEDY", "difficulty": "MEDIUM"},
    {"slug": "magic_toaster_rocket_short", "title": "Die Zauber-Toaster Rakete", "concept": "Toastbrot katapultiert Fruchtstücke wie Raketen in den Himmel.", "hook": "Toaster zählt 3-2-1 herunter.", "mechanic": "LAUNCHER_PHYSICS", "difficulty": "LOW"},
    {"slug": "grape_fairy_lights_tree_short", "title": "Trauben Lichterketten-Baum", "concept": "Trauben schalten sich wie bunte Glühbirnen an.", "hook": "Dunkles Zimmer erstrahlt plötzlich neonbunt.", "mechanic": "LIGHTING_ILLUMINATION", "difficulty": "LOW"},
    {"slug": "superfruit_avengers_assemble_short", "title": "Superfrucht Avengers Assemble", "concept": "Alle Früchte posieren mit Superhelden-Masken im Kreis.", "hook": "Blitzschlag enthüllt Frucht-Helden-Team.", "mechanic": "HERO_TEAMWORK", "difficulty": "MEDIUM"},
]


def generate_backlog_specifications() -> Dict[str, Any]:
    """Generates complete technical specifications for all 15 backlog items."""
    RUNTIME_CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    packages: List[Dict[str, Any]] = []

    for idx, seed in enumerate(SEEDS, start=11):
        label = f"VIDEO_{idx:02d}"
        slug = seed["slug"]
        pkg_spec = {
            "label": label,
            "slug": slug,
            "working_title": seed["title"],
            "target_format": {
                "width": 720,
                "height": 1280,
                "aspect_ratio": "9:16",
                "duration_seconds": 8.0,
                "fps": 30,
                "total_frames": 240,
                "video_codec": "h264",
                "audio_codec": "aac",
            },
            "creative_concept": {
                "summary": seed["concept"],
                "visual_hook": seed["hook"],
                "mechanic": seed["mechanic"],
                "production_difficulty": seed["difficulty"],
                "target_audience": "Kids & Family / Casual Shorts",
            },
            "storyboard_timeline": {
                "act_1_hook": {"time_range": "0.0s - 2.0s", "focus": seed["hook"], "camera": "Dynamic Zoom-In"},
                "act_2_escalation": {"time_range": "2.0s - 6.0s", "focus": seed["concept"], "camera": "Tracking Medium Shot"},
                "act_3_payoff_loop": {"time_range": "6.0s - 8.0s", "focus": "Surprise ending transitioning cleanly into loop", "camera": "Impact Freeze & Reset"},
            },
            "audio_synthesis_spec": {
                "melody_scale": "PENTATONIC_MAJOR",
                "bpm": 128,
                "sound_effects": [
                    {"time": 0.5, "fx": "SWOOSH_WHOOSH"},
                    {"time": 3.0, "fx": "CARTOON_BOING"},
                    {"time": 6.5, "fx": "CONFETTI_POP"},
                ],
            },
            "qc_contract": {
                "required_verdict": "PASS",
                "max_silence_seconds": 0.5,
                "min_contrast_ratio": 3.0,
                "publication_authorized": False,
                "human_gate_required": True,
            },
        }
        packages.append(pkg_spec)

    manifest = {
        "mission_id": "MISSION_153G",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "total_backlog_items": len(packages),
        "target_audience": "Family-Friendly High-Velocity Shorts",
        "specs": packages,
    }

    BACKLOG_SPECS_FILE.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    res = generate_backlog_specifications()
    print(f"✅ Generated {res['total_backlog_items']} backlog package specs -> {BACKLOG_SPECS_FILE}")
