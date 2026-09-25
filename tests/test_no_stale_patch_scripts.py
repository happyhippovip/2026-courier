"""Guard against stale one-shot patch scripts (priority 8: tote Repo-Artefakte).

scripts/patch_*.py were one-shot string-replacement rewriters (server/app.py,
test files) committed as scratch. Re-running them today would corrupt live
sources. They are unreferenced; this test fails if any patch_*.py file
reappears anywhere in the checkout (excluding .git).
"""
from pathlib import Path


def test_no_stale_patch_scripts():
    repo = Path(__file__).parent.parent.resolve()
    offenders = sorted(
        str(p.relative_to(repo))
        for p in repo.rglob("patch_*.py")
        if ".git" not in p.parts
    )
    assert not offenders, f"stale one-shot patch scripts must be removed: {offenders}"
