import os
import zipfile
import pytest
from courier_runtime.workbook import apply, make_fixture, plan, read_cells


@pytest.fixture
def sample_sheet(tmp_path):
    cells = {
        "A1": "Description",
        "B1": "Value",
        "A2": "Revenue",
        "B2": 1000.50,
        "A3": "Cost",
        "B3": 500,
        "A4": "Margin",
        "B4": "=B2-B3"
    }
    return make_fixture(str(tmp_path / "financials.xlsx"), cells), cells


def test_float_and_int_type_preservation(sample_sheet):
    book, orig = sample_sheet
    receipt = apply(book, {"B2": 1250.75, "B3": 600}, grant_id="grant-wb-test")
    cells = read_cells(book)
    assert cells["B2"] == 1250.75
    assert isinstance(cells["B2"], float)
    assert cells["B3"] == 600
    assert isinstance(cells["B3"], int)
    assert receipt["untouched_cells_verified"] == 6


def test_adding_new_cells_in_new_row(sample_sheet):
    book, orig = sample_sheet
    # Add cells at row 10
    receipt = apply(book, {"A10": "Audit Note", "B10": 42}, grant_id="grant-wb-new-row")
    cells = read_cells(book)
    assert cells["A10"] == "Audit Note"
    assert cells["B10"] == 42
    # Original cells untouched
    assert cells["A1"] == "Description"
    assert cells["B4"] == "=B2-B3"


def test_invalid_cell_references_rejected(sample_sheet):
    book, _ = sample_sheet
    for bad_ref in ["1A", "AA", "A0", "A-1", "TOOLONG12345678"]:
        with pytest.raises(ValueError, match="bad cell reference"):
            plan(book, {bad_ref: 100})


def test_formula_injection_attempts_rejected(sample_sheet):
    book, _ = sample_sheet
    with pytest.raises(ValueError, match="only plain numbers and text"):
        plan(book, {"A1": "=SUM(A1:A10)"})
    with pytest.raises(ValueError, match="only plain numbers and text"):
        plan(book, {"A1": "=CMD|' /C calc'!A0"})


def test_modifying_existing_formula_cell_rejected(sample_sheet):
    book, _ = sample_sheet
    # B4 is "=B2-B3"
    with pytest.raises(ValueError, match="holds a formula; editing formulas is out of scope"):
        plan(book, {"B4": 100})


def test_atomic_replace_failure_leaves_file_intact(sample_sheet, monkeypatch):
    book, _ = sample_sheet
    orig_bytes = open(book, "rb").read()

    # Monkeypatch os.replace to simulate an unexpected error during file swap
    def fail_replace(src, dst):
        raise IOError("Simulated disk error during atomic replace")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(IOError, match="Simulated disk error during atomic replace"):
        apply(book, {"B2": 999}, grant_id="g-fail")

    # Original file is completely untouched
    assert open(book, "rb").read() == orig_bytes
