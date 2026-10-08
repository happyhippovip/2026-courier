import os
import zipfile
import pytest
from pathlib import Path

from courier_runtime.workbook import (
    apply,
    make_fixture,
    plan,
    read_cells,
)


def test_shared_strings_parsing(tmp_path):
    wb_file = tmp_path / "shared_strings.xlsx"
    cells = {
        "A1": "Alpha String",
        "A2": "Beta String",
        "B1": 100,
        "B2": 25.5,
        "C1": "=B1+B2",
    }
    make_fixture(str(wb_file), cells)

    read_data = read_cells(str(wb_file))
    assert read_data["A1"] == "Alpha String"
    assert read_data["A2"] == "Beta String"
    assert read_data["B1"] == 100
    assert read_data["B2"] == 25.5
    assert read_data["C1"] == "=B1+B2"


def test_apply_creates_new_row_and_cell(tmp_path):
    wb_file = tmp_path / "new_cells.xlsx"
    make_fixture(str(wb_file), {"A1": "Initial"})

    # Row 10 does not exist yet
    receipt = apply(str(wb_file), {"Z10": "Far away"}, grant_id="g-grant-10")
    assert receipt["grant_id"] == "g-grant-10"
    assert receipt["before_sha256"] != receipt["after_sha256"]

    read_data = read_cells(str(wb_file))
    assert read_data["A1"] == "Initial"
    assert read_data["Z10"] == "Far away"


def test_plan_validates_types_and_forbids_formula_mutation(tmp_path):
    wb_file = tmp_path / "formula.xlsx"
    make_fixture(str(wb_file), {"A1": 10, "A2": "=A1*2"})

    with pytest.raises(ValueError, match="holds a formula"):
        plan(str(wb_file), {"A2": 50})

    with pytest.raises(ValueError, match="only plain numbers and text"):
        plan(str(wb_file), {"A1": "=SUM(1, 2)"})


def test_apply_failure_cleans_up_temp_file(tmp_path, monkeypatch):
    wb_file = tmp_path / "fail_cleanup.xlsx"
    make_fixture(str(wb_file), {"A1": "Value"})

    import courier_runtime.workbook as wb_mod

    # Monkeypatch _sha256 to raise an error during apply execution
    orig_sha256 = wb_mod._sha256
    call_count = 0

    def fail_after_first(path):
        nonlocal call_count
        call_count += 1
        if call_count > 1:
            raise RuntimeError("Disk error simulated")
        return orig_sha256(path)

    monkeypatch.setattr(wb_mod, "_sha256", fail_after_first)

    with pytest.raises(RuntimeError, match="Disk error simulated"):
        apply(str(wb_file), {"A1": "New"}, grant_id="g-grant-err")

    # Verify no leaked .xlsx files in the directory other than fail_cleanup.xlsx
    xlsx_files = list(tmp_path.glob("*.xlsx"))
    assert xlsx_files == [wb_file]
