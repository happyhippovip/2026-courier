#!/usr/bin/env python3
"""
CLI tool: Verbindliche Prüfung und Normalisierung von Windows-Verbatim-Pfaden.
Gibt Exit-Code 0 bei gültigem Verbatim-Pfad, Exit-Code 1 bei Ablehnung/Mismatch.
"""
import argparse
import sys
import os

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

try:
    from courier_runtime.workspace import verify_verbatim_path
except ImportError:
    sys.path.append(os.getcwd())
    from courier_runtime.workspace import verify_verbatim_path


def main():
    parser = argparse.ArgumentParser(description="Verbindliche Verifikation eines Windows-Verbatim-Pfads.")
    parser.add_argument("path", type=str, help="Zu prüfender Verbatim-Pfad (z.B. \\\\?\\C:\\...)")
    parser.add_argument("--must-exist", action="store_true", default=False, help="Erfordert physische Existenz auf der Festplatte")
    parser.add_argument("--inside-workdir", type=str, default=None, help="Prüft Einschluss in autorisiertem Workspace")
    args = parser.parse_args()

    valid, result = verify_verbatim_path(
        args.path,
        must_exist=args.must_exist,
        inside_workdir=args.inside_workdir,
    )

    if valid:
        print(f"VERBATIM PATH VALID: '{result}'")
        sys.exit(0)
    else:
        print(f"VERBATIM PATH FAILED (REFUSED): {result}")
        sys.exit(1)


if __name__ == "__main__":
    main()
