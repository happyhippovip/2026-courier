#!/usr/bin/env python3
"""
CLI tool: Verbindliche Prüfung gegen unautorisierten Laufwerkswechsel (Scopebruch).
Gibt Exit-Code 0 bei zulässigem Drive-Scope, Exit-Code 1 bei unautorisiertem Laufwerkswechsel.
"""
import argparse
import sys
import os

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

try:
    from courier_runtime.workspace import check_drive_scope
except ImportError:
    sys.path.append(os.getcwd())
    from courier_runtime.workspace import check_drive_scope


def main():
    parser = argparse.ArgumentParser(description="Verbindliche Prüfung gegen Laufwerkswechsel als Scopebruch.")
    parser.add_argument("target", type=str, nargs="?", default=None, help="Zu prüfender Zielpfad")
    parser.add_argument("--workdir", type=str, default=None, help="Autorisiertes Arbeitsverzeichnis (Standard: CWD)")
    parser.add_argument("--target", dest="target_opt", type=str, default=None, help="Alternativer Zielpfad-Parameter")
    args = parser.parse_args()

    target = args.target_opt or args.target
    if not target:
        print("DRIVE SCOPE ERROR: target path required")
        sys.exit(2)

    workdir = args.workdir or os.getcwd()

    valid, msg = check_drive_scope(workdir, target)
    if valid:
        print(f"DRIVE SCOPE VALID: '{target}' conforms to workdir '{workdir}' ({msg})")
        sys.exit(0)
    else:
        print(f"DRIVE SCOPE FAILED (BREACH): {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
