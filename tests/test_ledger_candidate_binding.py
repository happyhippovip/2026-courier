"""Gate 1 pins for scripts/ledger_candidate_binding.py."""

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "core"))
sys.path.insert(0, str(ROOT / "scripts"))

from core_builders import golden_path, mixed_history  # noqa: E402
from courier_core.journal import Journal  # noqa: E402
from courier_core.projection import projection_hash, rebuild  # noqa: E402
import ledger_candidate_binding as lcb  # noqa: E402


def _fill(path, events):
    with Journal(path) as j:
        for event in events:
            j.append(event)


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def clean_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "f.txt").write_text("x")
    _git(repo, "add", "f.txt")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    return repo


def test_same_journal_and_rebuild_give_same_fingerprint(tmp_path, clean_repo):
    db = tmp_path / "courier.db"
    _fill(db, mixed_history())
    first = lcb.build_binding(db, clean_repo)
    assert first == lcb.build_binding(db, clean_repo)
    with Journal(db) as j:
        out = rebuild(j, tmp_path / "rebuilt.db")
    conn = sqlite3.connect(out)
    try:
        assert projection_hash(conn) == first["ledger_fingerprint"]
    finally:
        conn.close()
    assert first["status"] == "CANDIDATE" and first["journal_chain_ok"] is True
    assert len(first["source_sha"]) == 40 and len(first["tree"]) == 40


def test_tampered_event_is_not_bindable_and_exits_nonzero(tmp_path, clean_repo):
    db = tmp_path / "courier.db"
    _fill(db, golden_path())
    with Journal(db) as j:
        conn = j.conn
        for (name,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='events'").fetchall():
            conn.execute(f'DROP TRIGGER "{name}"')
        conn.execute("UPDATE events SET payload = '{}' WHERE seq = 2")
    binding = lcb.build_binding(db, clean_repo)
    assert binding["journal_chain_ok"] is False
    assert binding["journal_first_bad_seq"] == 2
    assert binding["status"] == "NOT_BINDABLE"
    assert lcb.main(["--db", str(db), "--repo", str(clean_repo),
                     "--out", str(tmp_path / "b.json")]) != 0


def test_additional_event_changes_fingerprint(tmp_path, clean_repo):
    db_a, db_b = tmp_path / "a.db", tmp_path / "b.db"
    _fill(db_a, golden_path("t1"))
    _fill(db_b, golden_path("t1") + golden_path("t2"))
    a = lcb.build_binding(db_a, clean_repo)
    b = lcb.build_binding(db_b, clean_repo)
    assert a["ledger_fingerprint"] != b["ledger_fingerprint"]


def test_dirty_worktree_is_not_bindable(tmp_path, clean_repo):
    db = tmp_path / "courier.db"
    _fill(db, golden_path())
    (clean_repo / "f.txt").write_text("changed")
    binding = lcb.build_binding(db, clean_repo)
    assert binding["dirty"] is True
    assert binding["status"] == "NOT_BINDABLE"


def test_out_does_not_follow_a_symlink(tmp_path, clean_repo):
    db = tmp_path / "courier.db"
    _fill(db, golden_path())
    outside = tmp_path / "outside.json"
    outside.write_text("keep", encoding="utf-8")
    link = tmp_path / "binding.json"
    link.symlink_to(outside)
    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (outside_dir / "keep.txt").write_text("keep", encoding="utf-8")
    linked_dir = tmp_path / "linked-dir"
    linked_dir.symlink_to(outside_dir)
    file_code = lcb.main(["--db", str(db), "--repo", str(clean_repo), "--out", str(link)])
    dir_code = lcb.main(["--db", str(db), "--repo", str(clean_repo), "--out", str(linked_dir / "binding.json")])
    leaked = sorted(p.name for p in outside_dir.iterdir())
    assert file_code == 2 and dir_code == 2 and outside.read_text(encoding="utf-8") == "keep" and leaked == ["keep.txt"] and link.is_symlink(), (
        file_code, dir_code, outside.read_text(encoding="utf-8")[:80], leaked, link.is_symlink(),
    )
    real = tmp_path / "real.json"
    real_code = lcb.main(["--db", str(db), "--repo", str(clean_repo), "--out", str(real)])
    assert real_code != 2 and real.is_file() and "schema" in real.read_text(encoding="utf-8")


def test_status_is_never_pass(tmp_path, clean_repo):
    db = tmp_path / "courier.db"
    _fill(db, mixed_history())
    statuses = {lcb.build_binding(db, clean_repo)["status"]}
    (clean_repo / "f.txt").write_text("dirty")
    statuses.add(lcb.build_binding(db, clean_repo)["status"])
    assert statuses <= {"CANDIDATE", "NOT_BINDABLE"}
    assert "PASS" not in statuses
