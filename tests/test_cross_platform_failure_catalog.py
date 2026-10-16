"""Pins the cross-platform failure catalog against the tests it cites."""

from pathlib import Path

import pytest

from scripts.cross_platform_failure_catalog import (
    CatalogError,
    ENTRIES,
    check_catalog,
)


ROOT = Path(__file__).resolve().parents[1]


def test_shipped_catalog_matches_cited_tests():
    report = check_catalog(ROOT, ENTRIES)
    assert report["ok"] is True
    assert report["failures"] == []
    assert {item["id"] for item in report["entries"]} == {item["id"] for item in ENTRIES}
    again = check_catalog(ROOT, ENTRIES)
    assert again == report


def test_catalog_rejects_unknown_marker_and_missing_file(tmp_path):
    cited = tmp_path / "tests"
    cited.mkdir()
    (cited / "real.py").write_text('pytest.skip("real marker")\n', encoding="utf-8")
    good = {
        "id": "good",
        "platform": "win32",
        "kind": "skip",
        "test": "tests/real.py",
        "marker": "real marker",
    }
    assert check_catalog(tmp_path, (good,))["ok"] is True

    missing_marker = dict(good, id="bad-marker", marker="not in file")
    escaped = dict(good, id="escape", test="../real.py")
    absent = dict(good, id="absent", test="tests/missing.py")
    duplicate = (good, dict(good))
    empty_id = dict(good, id="")

    for entries in ((missing_marker,), (escaped,), (absent,), duplicate, (empty_id,), ()):
        report = check_catalog(tmp_path, entries)
        assert report["ok"] is False
        assert report["failures"]
        with pytest.raises(CatalogError):
            check_catalog(tmp_path, entries, strict=True)
