import zipfile

import pytest

from courier_runtime.workbook import apply, make_fixture, plan, read_cells

CELLS = {"A1": "Item", "B1": "Price", "A2": "Plan", "B2": 99, "A3": "Tax", "B3": 0.19, "B4": "=B2*(1+B3)"}


@pytest.fixture
def book(tmp_path):
    return make_fixture(str(tmp_path / "prices.xlsx"), CELLS)


def test_understand_reads_values_and_formulas(book):
    assert read_cells(book) == CELLS


def test_plan_previews_without_writing(book):
    before = open(book, "rb").read()
    assert plan(book, {"B2": 129, "C1": "Note"}) == [("B2", 99, 129), ("C1", None, "Note")]
    assert open(book, "rb").read() == before


def test_apply_changes_only_requested_cells_and_returns_receipt(book):
    receipt = apply(book, {"B2": 129, "C1": "Note"}, grant_id="g-fs-1")
    after = read_cells(book)
    assert after["B2"] == 129 and after["C1"] == "Note"
    assert {k: v for k, v in after.items() if k not in ("B2", "C1")} == {k: v for k, v in CELLS.items() if k != "B2"}
    assert receipt["before_sha256"] != receipt["after_sha256"] and receipt["untouched_cells_verified"] == 6
    assert receipt["grant_id"] == "g-fs-1"
    with zipfile.ZipFile(book) as z:
        assert z.testzip() is None


def test_no_grant_no_write(book):
    before = open(book, "rb").read()
    with pytest.raises(PermissionError):
        apply(book, {"B2": 1}, grant_id="")
    assert open(book, "rb").read() == before


@pytest.mark.parametrize("changes", [{"B4": 5}, {"B2": "=1+1"}, {"b2": 5}, {"A1": object()}])
def test_formulas_bad_refs_and_odd_values_are_refused(book, changes):
    before = open(book, "rb").read()
    with pytest.raises(ValueError):
        apply(book, changes, grant_id="g")
    assert open(book, "rb").read() == before
