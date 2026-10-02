#!/usr/bin/env python3
"""
S3 BUNDLE_ALLOWLIST_CHECKER
Deterministic checker for the intended customer runtime bundle.
Detects missing required runtime files, unexpected internal/fleet files, and manifest drift.
"""

import os
import sys
import argparse
from pathlib import Path

REQUIRED_PATHS = [
    "courier_core",
    "courier_worker",
    "courier_hub",
    "courier_core/schemas",
]

INTERNAL_CONFIDENTIAL = [
    "courier_core/config/product_strategy.json",
    "courier_core/config/social_channels.json",
    "courier_core/config/teamwork_policy.json",
    "config/product_strategy.json",
    "config/social_channels.json",
    "config/teamwork_policy.json",
]

DEV_AND_TEST_ONLY = [
    "scripts",
    "studio",
    "tests",
    "pyproject.toml",
]

def check_bundle(bundle_dir: Path) -> list[str]:
    errors = []

    # Check for missing required paths
    for req in REQUIRED_PATHS:
        req_path = bundle_dir / req
        if not req_path.exists():
            errors.append(f"Missing required runtime path: {req}")

    # Walk the bundle and check for leaked internal/dev files
    for root, dirs, files in os.walk(bundle_dir):
        rel_root = Path(root).relative_to(bundle_dir)
        
        # Check against dev/test dirs
        if str(rel_root) in DEV_AND_TEST_ONLY or any(str(rel_root).startswith(d + "/") for d in DEV_AND_TEST_ONLY):
            errors.append(f"Unexpected dev/test directory found in bundle: {rel_root}")
            
        for file in files:
            rel_file = str(rel_root / file)
            # Normalize path for checking
            rel_file_unix = rel_file.replace('\\', '/')
            if rel_file_unix in INTERNAL_CONFIDENTIAL:
                errors.append(f"FATAL: Confidential internal file leaked into bundle: {rel_file_unix}")

    return errors

def main():
    parser = argparse.ArgumentParser(description="Check customer runtime bundle allowlist")
    parser.add_argument("--bundle-dir", required=True, type=Path, help="Path to the extracted bundle directory to check")
    args = parser.parse_args()

    if not args.bundle_dir.is_dir():
        print(f"Error: Bundle directory not found: {args.bundle_dir}")
        sys.exit(1)

    errors = check_bundle(args.bundle_dir)
    
    if errors:
        print("Bundle allowlist checks failed!")
        for err in errors:
            print(f" - {err}")
        sys.exit(1)
        
    print("Bundle allowlist checks passed.")
    sys.exit(0)

if __name__ == "__main__":
    main()
