"""Guard against stale one-shot patch scripts (priority 8: tote Repo-Artefakte).

scripts/patch_*.py were one-shot string-replacement rewriters (server/app.py,
test files) committed as scratch. Re-running them today would corrupt live
sources. They are unreferenced; this test fails if any patch_*.py file
reappears under scripts/ (the live importable location). Root/archive
scratch history is out of scope for this guard.
"""
from pathlib import Path


def test_no_stale_patch_scripts():
    scripts = Path(__file__).parent.parent.resolve() / "scripts"
    offenders = sorted(str(p.relative_to(scripts)) for p in scripts.glob("patch_*.py"))
    assert not offenders, f"stale one-shot patch scripts must be removed: {offenders}"
