#!/usr/bin/env python3
"""
Product Shell Build Skeleton (Gated)
Status: PREPARED / LOCKED
Authority: Playbook Phase 8 - Product Shell only unlocked after positive pilot signal.
"""

import os
import sys
import json
from pathlib import Path

def build_product_shell(dry_run=True):
    repo_root = Path(__file__).resolve().parent.parent
    
    # Gate check: Fails closed unless positive pilot signal is durably confirmed
    pilot_gate_file = repo_root / "ops/ai/PILOT_READINESS_DECLARATION.md"
    pilot_unlocked = False
    
    if pilot_gate_file.exists():
        content = pilot_gate_file.read_text(encoding="utf-8")
        if "PRODUCT_SHELL_UNLOCKED=YES" in content:
            pilot_unlocked = True
            
    if not pilot_unlocked:
        print("[BUILD GATE LOCKED] Core proof and positive pilot signal required before building Product Shell.")
        print("Reference: ops/ai/END_TO_END_FINISH_TO_PILOT_PLAYBOOK_2026-09-27.md (Phase 8).")
        return 1

    artifact = repo_root / "dist" / "courier-product-shell"
    if not artifact.exists():
        print("[BUILD SKELETON] Distribution artifact is absent; skeleton verification did not run.")
        print(f"Missing: {artifact}")
        return 1

    print("[BUILD SKELETON] Completed skeleton verification successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(build_product_shell())
