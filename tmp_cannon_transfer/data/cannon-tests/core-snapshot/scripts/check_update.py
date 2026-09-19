#!/usr/bin/env python3
import subprocess
import json
import os
import sys

def run_bounded_check():
    """
    Führt einen isolierten, zeitbegrenzten Update-Check durch.
    Kein endloses Polling. Wird nur on-demand (Start, Wake, Button, CLI) aufgerufen.
    """
    try:
        # Bounded network fetch (max 10 seconds)
        subprocess.run(
            ["git", "fetch", "origin"],
            timeout=10,
            capture_output=True,
            text=True
        )

        # Get local and remote HEADs for the current branch
        branch_proc = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True)
        branch = branch_proc.stdout.strip()
        
        if branch == "HEAD":
            # Detached head, can't easily compare to upstream
            return {"status": "UNKNOWN", "message": "Detached HEAD", "update_available": False}

        local_proc = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        local_head = local_proc.stdout.strip()

        remote_proc = subprocess.run(["git", "rev-parse", f"origin/{branch}"], capture_output=True, text=True)
        if remote_proc.returncode != 0:
            return {"status": "UNKNOWN", "message": "No upstream branch found", "update_available": False}
            
        remote_head = remote_proc.stdout.strip()

        # Check if we are behind
        # git rev-list HEAD..origin/branch --count
        rev_list_proc = subprocess.run(
            ["git", "rev-list", f"{local_head}..{remote_head}", "--count"],
            capture_output=True, text=True, check=True
        )
        commits_behind = int(rev_list_proc.stdout.strip())

        update_available = commits_behind > 0

        return {
            "status": "SUCCESS",
            "update_available": update_available,
            "commits_behind": commits_behind,
            "local_head": local_head,
            "remote_head": remote_head,
            "branch": branch
        }

    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "message": "Git fetch timed out", "update_available": False}
    except Exception as e:
        return {"status": "ERROR", "message": str(e), "update_available": False}

if __name__ == "__main__":
    result = run_bounded_check()
    print(json.dumps(result, indent=2))
