"""R2: golden regression fixtures for the Repo Reality Check report.

Three tiny synthetic repos (clean, messy, secrets-in-fixtures) are built
under tmp_path and their full markdown report is compared byte-for-byte
against golden snapshots in tests/repo_reality_report_golden/.

No network, no customer code execution, no real secret material: the only
secret-shaped value is the synthetic token "example-token-value", which the
report must never echo (counts and paths only).

Regenerate goldens after an intentional report change with:
    UPDATE_GOLDEN=1 python -m pytest tests/test_repo_reality_report_fixtures.py -q
then review the diff before committing.
"""

import os
from pathlib import Path

from courier_core.repo_reality_report import analyze, build_report

GOLDEN_DIR = Path(__file__).resolve().parent / "repo_reality_report_golden"
SYNTHETIC_TOKEN = "example-token-value"


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _clean(repo: Path) -> None:
    _write(repo, "README.md", "# Demo\n")
    _write(repo, "LICENSE", "synthetic\n")
    _write(repo, ".gitignore", "venv/\n")
    _write(repo, "tests/test_app.py", "def test_ok():\n    pass\n")
    _write(
        repo,
        ".github/workflows/ci.yml",
        "name: CI\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n",
    )
    _write(repo, "requirements.txt", "flask==1.0.0\n")


def _messy(repo: Path) -> None:
    # No README, LICENSE, .gitignore, CI config, or pinned deps on purpose.
    _write(repo, "src/app.py", "TODO\nFIXME\nHACK\nx = 1\n")
    _write(repo, "requirements.txt", "requests>=2.0\nnumpy\n")
    _write(repo, "test_scratch.py", "def test_root():\n    pass\n")
    _write(repo, "scratch/note.txt", "hi\n")


def _secrets_in_fixtures(repo: Path) -> None:
    _clean(repo)
    _write(repo, "tests/fixtures/sample.env", f'password = "{SYNTHETIC_TOKEN}"\n')


BUILDERS = {
    "clean": _clean,
    "messy": _messy,
    "secrets_in_fixtures": _secrets_in_fixtures,
}


def _check(name: str, tmp_path: Path) -> None:
    repo = tmp_path / name
    repo.mkdir()
    BUILDERS[name](repo)
    text = build_report(repo)
    golden = GOLDEN_DIR / f"{name}.md"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN_DIR.mkdir(exist_ok=True)
        golden.write_text(text, encoding="utf-8")
    assert golden.is_file(), f"missing golden snapshot: {golden}"
    assert text == golden.read_text(encoding="utf-8")
    # The report carries counts and relative paths only.
    assert str(repo) not in text
    assert str(tmp_path) not in text
    assert SYNTHETIC_TOKEN not in text


def test_golden_clean(tmp_path):
    _check("clean", tmp_path)


def test_golden_messy(tmp_path):
    _check("messy", tmp_path)


def test_golden_secrets_in_fixtures(tmp_path):
    _check("secrets_in_fixtures", tmp_path)


def test_golden_scores_are_ordered(tmp_path):
    scores = {}
    for name, build in BUILDERS.items():
        repo = tmp_path / f"score-{name}"
        repo.mkdir()
        build(repo)
        scores[name] = analyze(repo)["score"]["value"]
    assert scores["clean"] == 100
    assert scores["clean"] > scores["secrets_in_fixtures"] > scores["messy"]
