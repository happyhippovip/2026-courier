#!/usr/bin/env python3
"""Idea Sync & Thought Curator Engine for 2026 Courier.

Permanent idea-memory and context synchronization agent:
Human → Idea Sync → Chief Commander → Router → Worker Agents → Courier → Chief Review

Visual States:
- IDLE
- NEW IDEA
- READING MEMORY
- COMPARING
- DUPLICATE FOUND
- RELATED FOUND
- CONFLICT FOUND
- CONTEXT UPDATED
- SENT TO CHIEF
- DEFERRED
- PROMOTED
- BLOCKED

Memory Truth Rule:
- IDEA != VERIFIED
- IDEA != IMPLEMENTED
- USER_REPORTED != TECHNICALLY VERIFIED
- Never silently overwrite historical decisions.
- Deterministic/local comparison first (0.00 EUR cost).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
PROJECT_MEMORY_DIR = Path("/Users/user/Downloads/2026-project-memory")

EVENTS_DIR = COURIER_DIR / "events"
STATES_DIR = EVENTS_DIR / "agent-states"
THOUGHTS_DIR = EVENTS_DIR / "thoughts"

STATES_DIR.mkdir(parents=True, exist_ok=True)
THOUGHTS_DIR.mkdir(parents=True, exist_ok=True)

# Add scripts directory to path
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from run_antigravity_bridge import AntigravityVisualStateTracker, load_json, save_json
except ImportError:
    from scripts.run_antigravity_bridge import AntigravityVisualStateTracker, load_json, save_json


class ThoughtCurator:
    """Permanent idea-memory and context synchronization agent."""

    def __init__(self, repo_dir: Path = COURIER_DIR, memory_dir: Path = PROJECT_MEMORY_DIR):
        self.repo_dir = repo_dir
        self.memory_dir = memory_dir
        self.state_tracker = AntigravityVisualStateTracker(
            agent_id="agent-thought-curator",
            name="Thought Curator",
            role="Permanent Idea Sync & Memory Curator",
        )
        self.memory_index = self._index_project_memory()

    def _index_project_memory(self) -> dict[str, list[dict]]:
        """Indexes canonical memory entries for deterministic keyword and policy matching."""
        index = {
            "decisions": [],
            "ideas": [],
            "state_principles": [],
        }

        # 1. Index DECISIONS.md
        decisions_file = self.memory_dir / "DECISIONS.md"
        if decisions_file.exists():
            content = decisions_file.read_text(encoding="utf-8")
            for match in re.finditer(r"##\s+(D-\d+)\s+—\s+([^\n]+)([\s\S]*?)(?=\n##\s+D-\d+|\Z)", content):
                index["decisions"].append({
                    "id": match.group(1),
                    "title": match.group(2).strip(),
                    "body": match.group(3).strip(),
                })

        # 2. Index IDEA_ARCHIVE.md
        ideas_file = self.memory_dir / "IDEA_ARCHIVE.md"
        if ideas_file.exists():
            content = ideas_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                line_s = line.strip()
                if line_s.startswith("- **"):
                    index["ideas"].append({"entry": line_s})

        return index

    def curate_idea(self, raw_idea: str, idea_type: str = "IDEA") -> dict:
        """Processes a human idea through the full Thought Curator lifecycle."""
        normalized = " ".join(raw_idea.strip().lower().split())
        idea_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
        idea_id = f"idea-{idea_hash}"
        tokens = set(re.findall(r"\w+", normalized))

        print(f"\n[THOUGHT_CURATOR] Ingesting Human {idea_type}: '{raw_idea[:80]}' (ID: {idea_id})")

        # 1. State: NEW IDEA
        self.state_tracker.update_state(
            state="NEW IDEA",
            task=f"Ingested {idea_id}",
            progress=0.15,
            workflow=idea_id,
            last_action=f"Ingested human {idea_type.lower()}: '{raw_idea[:60]}'",
            next_action="Opening canonical Project Memory index",
            blocked=False,
            human_gate=None,
        )

        # 2. State: READING MEMORY
        self.state_tracker.update_state(
            state="READING MEMORY",
            task=f"Reading memory for {idea_id}",
            progress=0.35,
            workflow=idea_id,
            last_action="Scanning DECISIONS.md, IDEA_ARCHIVE.md, and PROJECT_STATE.md",
            next_action="Comparing semantic tokens & policy rules",
            blocked=False,
            human_gate=None,
        )

        # 3. State: COMPARING
        self.state_tracker.update_state(
            state="COMPARING",
            task=f"Comparing {idea_id}",
            progress=0.55,
            workflow=idea_id,
            last_action="Evaluating policy compliance and checking prior duplicate/related concepts",
            next_action="Formulating Context Delta package",
            blocked=False,
            human_gate=None,
        )

        conflicts = []
        related_entries = []
        memory_links = []
        classification = "NEW"

        # Check for policy conflicts
        # Policy D-002: Crypto / speculation forbidden
        crypto_keywords = ["crypto", "krypto", "token", "memecoin", "leverage", "trading", "fomo", "hebel", "spekulation"]
        if any(kw in normalized for kw in crypto_keywords):
            conflicts.append({
                "rule": "D-002 — Crypto and speculative recovery blocked",
                "severity": "CRITICAL_REJECT",
                "reason": "Crypto trading, memecoins, and token speculation are strictly forbidden by project policy."
            })
            memory_links.append({"type": "DECISION", "id": "D-002", "title": "Crypto and speculative recovery blocked", "status": "VIOLATION"})
            classification = "CONFLICT FOUND"

        # Policy D-004: Paid action without gate
        paid_keywords = ["kauf", "pay", "credit", "subscription", "kostenpflichtig", "anzeigen schalten", "werbung kaufen", "fremdkapital"]
        if any(kw in normalized for kw in paid_keywords):
            conflicts.append({
                "rule": "D-004 — No paid or irreversible action by default",
                "severity": "HUMAN_GATE_REQUIRED",
                "reason": "Paid services, credit purchases or ad spending require explicit human approval."
            })
            memory_links.append({"type": "DECISION", "id": "D-004", "title": "No paid or irreversible action by default", "status": "HUMAN_GATE"})
            if classification != "CONFLICT FOUND":
                classification = "CONFLICT FOUND"

        # Policy D-022: Scoped permissions & safe cleanup
        cleanup_keywords = ["rm -rf", "delete all", "force push", "sudo", "lösche alles", "format"]
        if any(kw in normalized for kw in cleanup_keywords):
            conflicts.append({
                "rule": "D-022 — Scoped permissions and safe cleanup",
                "severity": "CRITICAL_REJECT",
                "reason": "Destructive shell commands or unconstrained cleanup are blocked by policy."
            })
            memory_links.append({"type": "DECISION", "id": "D-022", "title": "Scoped permissions and safe cleanup", "status": "VIOLATION"})
            classification = "CONFLICT FOUND"

        # Check for related entries in IDEA_ARCHIVE.md
        for idea_item in self.memory_index.get("ideas", []):
            entry_text = idea_item["entry"].lower()
            entry_tokens = set(re.findall(r"\w+", entry_text))
            common = tokens.intersection(entry_tokens) - {"and", "or", "the", "for", "with", "in", "to", "und", "der", "die", "das", "ein", "eine", "für", "mit"}
            if len(common) >= 3:
                related_entries.append(idea_item["entry"])
                clean_name = idea_item["entry"].split(":**")[0].replace("- **", "") if ":**" in idea_item["entry"] else "IDEA"
                memory_links.append({"type": "ARCHIVED_IDEA", "id": clean_name, "title": idea_item["entry"][:60], "status": "RELATED"})

        if related_entries and classification != "CONFLICT FOUND":
            classification = "RELATED FOUND"

        # Identify affected components / agents
        affected_components = []
        if any(k in normalized for k in ["short", "godot", "render", "video", "fruitki", "strawberry", "kiwi", "3d", "media"]):
            affected_components.append("3D Shorts Pipeline (Antigravity Media Studio)")
        if any(k in normalized for k in ["syntax", "audit", "lint", "test", "review", "code", "schema", "qa"]):
            affected_components.append("Code Verification & QA (Codex Lab)")
        if not affected_components:
            affected_components.append("General Architecture (Courier System)")

        # Formulate Recommended Next Action & Target Agent
        qa_keywords = ["audit", "syntax", "unit test", "unit-test", "code review", "lint", "qa", "verifikation"]
        if classification == "CONFLICT FOUND":
            rec_action = "STOP_ON_POLICY_CONFLICT"
            target_agent = "chief_gate"
        elif any(kw in normalized for kw in qa_keywords):
            rec_action = "ROUTE_TO_CODEX_QA"
            target_agent = "codex"
        else:
            rec_action = "ROUTE_TO_ANTIGRAVITY_PRIMARY"
            target_agent = "antigravity"

        # 4. State: CONTEXT UPDATED
        self.state_tracker.update_state(
            state="CONTEXT UPDATED",
            task=f"Context assembled for {idea_id}",
            progress=0.85,
            workflow=idea_id,
            last_action=f"Assembled Context Delta with {len(memory_links)} memory links",
            next_action="Forwarding Context Delta to Chief Commander",
            blocked=False,
            human_gate=None,
        )

        # Final Context Delta
        context_delta = {
            "idea_id": idea_id,
            "raw_idea": raw_idea,
            "normalized_idea": normalized,
            "type": idea_type,
            "classification": classification,
            "truth_boundary": "IDEA != VERIFIED | USER_REPORTED != TECHNICALLY_VERIFIED",
            "conflicts": conflicts,
            "related_memory_entries": related_entries[:3],
            "memory_links": memory_links,
            "affected_components": affected_components,
            "recommended_next_action": rec_action,
            "target_agent_recommendation": target_agent,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        # 5. Final State: SENT TO CHIEF or BLOCKED
        final_state = "BLOCKED" if classification == "CONFLICT FOUND" else "SENT TO CHIEF"
        self.state_tracker.update_state(
            state=final_state,
            task=f"Curated {idea_id}",
            progress=1.0,
            workflow=idea_id,
            last_action=f"Classified as {classification} -> Recommendation: {rec_action}",
            next_action=f"Forwarding to Chief Commander (Agent: {target_agent})" if final_state == "SENT TO CHIEF" else "Awaiting human override or reformulation",
            result=f"Classification: {classification} | Links: {len(memory_links)}",
            blocked=final_state == "BLOCKED",
            human_gate="REQUIRE_HUMAN_CONFIRMATION" if final_state == "BLOCKED" else None,
        )

        # Save thought record
        thought_file = THOUGHTS_DIR / f"{idea_id}.json"
        save_json(thought_file, context_delta)

        return context_delta


def main():
    parser = argparse.ArgumentParser(description="Curate Human Ideas against Project Memory")
    parser.add_argument("--idea", type=str, required=True, help="Human idea or strategic thought")
    parser.add_argument("--type", type=str, default="IDEA", choices=["IDEA", "THOUGHT", "STRATEGY", "GOAL"])
    args = parser.parse_args()

    curator = ThoughtCurator()
    res = curator.curate_idea(args.idea, args.type)
    print("\n=== CURATION SUMMARY ===")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
