"""Guard against stale backup duplicates (priority 8: tote Repo-Artefakte).

Freeze commit 6ca172ac once committed *.bak copies next to their live
originals. Pytest never collects backup copies, so they are dead weight
that confuses collision checks. This test fails if any backup-style file
(*.bak, *.bak2, *.before-*) exists anywhere in the checkout (excluding .git).
"""
from pathlib import Path

STALE_PATTERNS = ("*.bak*", "*.before-*")


def _iter_offenders(repo: Path):
    seen = set()
    for pattern in STALE_PATTERNS:
        for p in repo.rglob(pattern):
            if ".git" in p.parts:
                continue
            if not p.is_file():
                continue
            rel = str(p.relative_to(repo))
            if rel not in seen:
                seen.add(rel)
                yield rel


def test_no_stale_bak_artifacts():
    repo = Path(__file__).parent.parent.resolve()
    offenders = sorted(_iter_offenders(repo))
    assert not offenders, f"stale backup duplicates must be removed: {offenders}"
