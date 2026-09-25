"""Guard against stale backup duplicates (priority 8: tote Repo-Artefakte).

Freeze commit 6ca172ac once committed *.bak copies next to their live
originals; a *.bak2 backup of agent_handoff_ledger.py survived the *.bak
cleanup because the old glob missed suffixed variants. Pytest never
collects these, so they are dead weight that confuses collision checks.
This test fails if any backup-suffixed file (*.bak, *.bak2, ...) exists
anywhere in the checkout (excluding .git).
"""
from pathlib import Path


def test_no_stale_bak_artifacts():
    repo = Path(__file__).parent.parent.resolve()
    offenders = sorted(
        str(p.relative_to(repo))
        for p in repo.rglob("*.bak*")
        if ".git" not in p.parts
    )
    assert not offenders, f"stale backup duplicates must be removed: {offenders}"
