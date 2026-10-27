"""[DRUIDE | ACCOUNT 2] K6: the RUNBOOK tables are checked against the code, so they cannot drift silently."""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from tools.automation import ci_watcher_v2 as w  # noqa: E402
from tools.automation import journal_export as je  # noqa: E402

TEXT = (Path(__file__).resolve().parent / "RUNBOOK.md").read_text(encoding="utf-8")


def table_rows(heading_start):
    """Rows `| code | ... |` of the first table after a line that starts with `heading_start`."""
    lines = TEXT.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(heading_start))
    rows = []
    for line in lines[start + 1:]:
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells[0].isdigit():
                rows.append(cells)
        elif rows:
            break
    return rows


def test_k6_the_exporter_table_lists_exactly_the_exit_codes_of_the_code():
    codes = {je.EXIT_OK, je.EXIT_USAGE, je.EXIT_UNREADABLE, je.EXIT_BAD_CHAIN, je.EXIT_BAD_FOLD, je.EXIT_WRITE, je.EXIT_CHANGED, je.EXIT_HEAD_MISMATCH}
    rows = table_rows("Exporter `python -m")
    assert {int(r[0]) for r in rows} == codes and len(rows) == len(codes)
    assert codes == {0, 2, 3, 4, 5, 6, 7, 8}


def test_k6_the_watcher_table_lists_exactly_the_exit_codes_and_status_names_of_the_code():
    rows = table_rows("Watcher `python -m")
    assert {int(r[0]) for r in rows} == set(w.EXIT_CODES.values()) | {2} and len(rows) == len(set(w.EXIT_CODES.values())) + 1
    for status, code in w.EXIT_CODES.items():
        if status in ("RESET", "NO_STATE"):
            continue
        row = next(r for r in rows if int(r[0]) == code)
        assert status.replace("DISPATCH_UNCONFIRMED", "DISPATCH_UNCONFIRMED") in row[1], (status, row)


@pytest.mark.parametrize("heading", ["## Restart", "## Stale lock", "## DISPATCH_UNCONFIRMED", "## Rollback", "## Exit codes"])
def test_k6_the_runbook_has_the_sections(heading):
    assert any(line.startswith(heading) for line in TEXT.splitlines())


def test_k6_the_files_named_in_the_stale_lock_section_match_the_code(tmp_path):
    lock = w._Lock(tmp_path / ".ci-watch-x.lock")
    assert lock.excl_path.name == ".ci-watch-x.lock.x"
    guard = lock._takeover_guard(lock.path.parent.stat())
    assert guard.name.startswith(".ci-watch-x.lock.x.take-")
    assert ".ci-watch-<key>.lock.x" in TEXT and ".lock.x.take-*" in TEXT


def test_k6_the_stale_limit_in_the_restart_section_is_the_formula_of_the_code():
    assert "max(600, 3*max_interval+300)" in TEXT
    source = (Path(w.__file__)).read_text(encoding="utf-8")
    assert "stale_after=max(600.0, 3 * backoff.max_interval + 300.0)" in source
