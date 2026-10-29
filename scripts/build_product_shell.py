#!/usr/bin/env python3
"""
Product shell prep skeleton (gated).

Status: PREP / LOCKED. This file does not build an installer.

Authority: Playbook Phase 8, after a positive pilot signal.
J-1 (ops/ai/USER_ACCEPTANCE_J_PRODUCT_SHELL_GATE.md) requires all of:
a GREEN signal from the unified metric dictionary, a core-freeze record
from physical RUN_1/RUN_2 evidence, named pilot cohort evidence, and an
explicit human unlock citing those three. J-3: a standalone YES flag is
invalid. No machine-readable bundle of that proof is accepted here, so
declaration prose cannot unlock.
"""

import sys
from pathlib import Path

# Prep steps only. They are not an installer and must not be labeled READY.
SKELETON_STAGES = (
    "1. Validate source bundle & commit SHA",
    "2. Compile client assets (Connect -> Goal -> Status drawer)",
    "3. Bundle lightweight Python server runtime",
    "4. Generate release metadata & reproducible package manifest",
    "5. Output distribution artifact to dist/courier-product-shell",
)


def declaration_has_authoritative_j1_unlock(content: str) -> bool:
    """Return whether declaration text is an authoritative J-1 unlock.

    It is not. Markdown prose is not pilot GREEN evidence, a core-freeze
    record, named cohort evidence, or a human unlock citing those three.
    Unstructured, negated, stuffed, or lone structured YES lines
    (PRODUCT_SHELL_UNLOCKED=YES or PRODUCT_SHELL_UNLOCKED: YES) are the
    same as a missing flag: locked. This gate does not invent a replacement
    GO signal.
    """
    if not isinstance(content, str) or content == "":
        return False
    # Every remaining string, including a structured YES line, lacks the
    # J-1 evidence bundle. Reject the whole class.
    return False


def skeleton_report_lines():
    """Lines for the prep listing. Reached only after a real unlock."""
    lines = [
        "[BUILD SKELETON] Prep skeleton only. No installer was produced.",
    ]
    for stage in SKELETON_STAGES:
        lines.append(f"  -> {stage} (PREP/SKELETON)")
    lines.append(
        "[BUILD SKELETON] Skeleton listing finished. Product shell remains unbuilt."
    )
    return lines


def _read_declaration(path: Path):
    """Read declaration text. Undecodable or unreadable bytes stay locked."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def build_product_shell(dry_run=True):
    # Signature kept for callers. dry_run does not open the gate.
    del dry_run
    repo_root = Path(__file__).resolve().parent.parent
    pilot_gate_file = repo_root / "ops/ai/PILOT_READINESS_DECLARATION.md"
    pilot_unlocked = False

    if pilot_gate_file.exists():
        content = _read_declaration(pilot_gate_file)
        if content is not None:
            pilot_unlocked = declaration_has_authoritative_j1_unlock(content)

    if not pilot_unlocked:
        print(
            "[BUILD GATE LOCKED] Core proof and positive pilot signal "
            "required before building Product Shell."
        )
        print(
            "Declaration text is not J-1 proof. A YES token in that file "
            "does not unlock."
        )
        print(
            "Missing pilot GREEN signal, core-freeze record, named cohort "
            "evidence, or human unlock citing them."
        )
        print("Reference: ops/ai/USER_ACCEPTANCE_J_PRODUCT_SHELL_GATE.md (J-1, J-3).")
        print(
            "Reference: ops/ai/END_TO_END_FINISH_TO_PILOT_PLAYBOOK_2026-09-27.md "
            "(Phase 8)."
        )
        return 1

    for line in skeleton_report_lines():
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(build_product_shell())
