import os
import zipfile
import xml.etree.ElementTree as ET
import pytest

from scripts.generate_project_dashboard_xlsx import generate_dashboard, verify_dashboard_file, NS
from courier_runtime.workbook import read_cells


def test_generate_and_verify_dashboard_xlsx(tmp_path):
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    out_file = str(tmp_path / "test_dashboard.xlsx")

    git_info, counts = generate_dashboard(repo_dir, out_file)

    assert os.path.exists(out_file)
    assert git_info["head_sha"] != "UNKNOWN"

    expected_sheets = [
        "Project Milestones",
        "Ledger Workkeys",
        "Open PRs & CI",
        "Worker Fleet Status",
        "Packaging & Installers",
        "Costs & Budget",
        "Tests & Evidence",
        "Approvals & Actions"
    ]
    val = verify_dashboard_file(out_file, expected_sheets)

    assert val["sheets_count"] == 8
    assert val["sheet_names"] == expected_sheets
    assert val["total_rows"] >= 100
    assert val["total_cells"] >= 800

    # Verify courier_runtime.workbook can read cells from sheet 1
    cells = read_cells(out_file)
    assert "A1" in cells
    assert cells["A1"] == "Milestone_ID"
    assert "A2" in cells
    assert cells["A2"] == "M-V1-01"


def test_styles_and_freezing(tmp_path):
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    out_file = str(tmp_path / "test_styles.xlsx")
    generate_dashboard(repo_dir, out_file)

    with zipfile.ZipFile(out_file, "r") as z:
        # Check styles.xml
        styles_root = ET.fromstring(z.read("xl/styles.xml"))
        assert styles_root.tag == f"{{{NS}}}styleSheet"

        # Check sheet 1 freezing
        sheet1_root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        views = sheet1_root.find(f"{{{NS}}}sheetViews")
        assert views is not None
        pane = views.find(f".//{{{NS}}}pane")
        assert pane is not None
        assert pane.get("state") == "frozen"
        assert pane.get("ySplit") == "1"
