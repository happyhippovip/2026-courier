#!/usr/bin/env python3
"""
CLI tool: Verbindliche und authentische Ermittlung des Workspace-Roots.
Gibt Exit-Code 0 bei gültigem authentischem Workspace-Root, Exit-Code 1 bei Fehler/Ablehnung.
"""
import argparse
import sys
import os

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

try:
    from courier_runtime.workspace import (
        find_authentic_workspace_root,
        verify_workspace_root,
        AuthenticWorkspaceRootError,
    )
except ImportError:
    # Fallback if invoked from arbitrary working directory
    sys.path.append(os.getcwd())
    from courier_runtime.workspace import (
        find_authentic_workspace_root,
        verify_workspace_root,
        AuthenticWorkspaceRootError,
    )


def main():
    parser = argparse.ArgumentParser(description="Authentische Ermittlung des Workspace-Roots.")
    parser.add_argument("--path", type=str, default=None, help="Startpfad (default: CWD)")
    parser.add_argument("--expected-name", type=str, default=None, help="Erwarteter Repository-Name (z.B. 2026-courier)")
    args = parser.parse_args()

    valid, result = verify_workspace_root(args.path, expected_name=args.expected_name)
    if valid:
        print(f"AUTHENTIC WORKSPACE ROOT: '{result}'")
        sys.exit(0)
    else:
        print(f"AUTHENTIC WORKSPACE ROOT FAILED (REFUSED): {result}")
        sys.exit(1)


if __name__ == "__main__":
    main()
