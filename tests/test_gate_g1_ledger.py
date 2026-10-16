"""Gate G1 ledger gaps: runtime binding, no rewrite, unknown blocks.

Red before the fix: a clean chain with no append-only guards is still
CANDIDATE, a blank git identity exits 0, and the binding has no loaded
runtime and no seal.
"""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "core"))
sys.path.insert(0, str(ROOT / "scripts"))

from core_builders import golden_path  # noqa: E402
from courier_core.journal import Journal  # noqa: E402
import courier_core.build as build  # noqa: E402
import ledger_candidate_binding as lcb  # noqa: E402


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _fill(path, events):
    with Journal(path) as journal:
        for event in events:
            journal.append(event)


@pytest.fixture
def clean_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "f.txt").write_text("x")
    _git(repo, "add", "f.txt")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    return repo


def _db(tmp_path):
    db = tmp_path / "courier.db"
    _fill(db, golden_path())
    return db


def _drop_guards(db):
    conn = sqlite3.connect(db)
    try:
        for (name,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='events'").fetchall():
            conn.execute(f'DROP TRIGGER "{name}"')
        conn.commit()
    finally:
        conn.close()


def test_binding_pins_the_loaded_runtime_and_a_seal(tmp_path, clean_repo):
    db = _db(tmp_path)
    binding = lcb.build_binding(db, clean_repo)
    runtime = binding["runtime"]
    assert runtime["source_sha256"] == build.build_identity()["source_sha256"]
    assert runtime["version"] == build.build_identity()["version"]
    assert binding["source_sha"] != runtime["source_sha256"]
    assert binding["guards_present"] is True
    assert lcb.binding_intact(binding) is True
    assert lcb.build_binding(db, clean_repo) == binding


def test_rewriting_the_runtime_breaks_the_seal(tmp_path, clean_repo):
    binding = lcb.build_binding(_db(tmp_path), clean_repo)
    binding["runtime"]["source_sha256"] = "0" * 64
    assert lcb.binding_intact(binding) is False
    assert lcb.accepted(binding) is False


def test_missing_append_only_guards_are_not_bindable(tmp_path, clean_repo):
    db = _db(tmp_path)
    _drop_guards(db)
    binding = lcb.build_binding(db, clean_repo)
    assert binding["guards_present"] is False
    assert "append_only_guards_missing" in binding["unknowns"]
    assert binding["status"] == "NOT_BINDABLE"
    assert lcb.main(["--db", str(db), "--repo", str(clean_repo),
                     "--out", str(tmp_path / "b.json")]) != 0
    written = json.loads((tmp_path / "b.json").read_text(encoding="utf-8"))
    assert written["status"] == "NOT_BINDABLE"


def test_blank_source_identity_is_not_success(tmp_path, clean_repo, monkeypatch):
    monkeypatch.setattr(lcb, "_git", lambda repo, *args: "")
    db = _db(tmp_path)
    binding = lcb.build_binding(db, clean_repo)
    assert "source_identity_unavailable" in binding["unknowns"]
    assert binding["status"] == "NOT_BINDABLE"
    assert binding["status"] != "CANDIDATE"
    assert lcb.main(["--db", str(db), "--repo", str(clean_repo)]) != 0


def test_unknown_loaded_runtime_blocks(tmp_path, clean_repo, monkeypatch):
    monkeypatch.setattr(build, "source_sha256", lambda: None)
    db = _db(tmp_path)
    binding = lcb.build_binding(db, clean_repo)
    assert "loaded_runtime_unknown" in binding["unknowns"]
    assert binding["status"] == "NOT_BINDABLE"
    assert lcb.accepted(binding) is False
    assert lcb.main(["--db", str(db), "--repo", str(clean_repo)]) != 0


def test_relabelled_unknown_is_not_accepted(tmp_path, clean_repo):
    binding = lcb.build_binding(_db(tmp_path), clean_repo)
    binding["status"] = "UNKNOWN"
    binding["seal"] = lcb.seal_of({k: v for k, v in binding.items() if k != "seal"})
    assert lcb.binding_intact(binding) is True
    assert lcb.accepted(binding) is False
