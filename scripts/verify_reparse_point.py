#!/usr/bin/env python3
"""
CLI tool: Verbindliche Prüfung und Absicherung von Windows-Reparse-Points (Junctions, Symlinks).
Gibt Exit-Code 0 bei sicherem/konformem Pfad, Exit-Code 1 bei Unconfined-Reparse-Point oder Policy-Verletzung.
"""
import argparse
import sys
import os

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

try:
    from courier_runtime.workspace import check_reparse_point_safety
except ImportError:
    sys.path.append(os.getcwd())
    from courier_runtime.workspace import check_reparse_point_safety


def main():
    parser = argparse.ArgumentParser(description="Verbindliche Absicherung von Windows-Reparse-Points.")
    parser.add_argument("path", type=str, nargs="?", default=None, help="Zu prüfender Pfad")
    parser.add_argument("--path", dest="path_opt", type=str, default=None, help="Alternativer Pfad-Parameter")
    parser.add_argument("--workdir", type=str, default=None, help="Autorisiertes Arbeitsverzeichnis (Standard: CWD)")
    parser.add_argument("--disallow-all", action="store_true", default=False, help="Verbietet jegliche Reparse-Points strikt")
    args = parser.parse_args()

    target = args.path_opt or args.path
    if not target:
        print("REPARSE POINT ERROR: path parameter required")
        sys.exit(2)

    workdir = args.workdir or os.getcwd()
    allow_confined = not args.disallow_all

    safe, msg = check_reparse_point_safety(target, workdir=workdir, allow_confined=allow_confined)
    if safe:
        print(f"REPARSE POINT SAFE: '{target}' ({msg})")
        sys.exit(0)
    else:
        print(f"REPARSE POINT REFUSED: '{target}' ({msg})")
        sys.exit(1)


if __name__ == "__main__":
    main()
