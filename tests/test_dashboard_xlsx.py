import os
import zipfile
import xml.etree.ElementTree as ET
import pytest
from unittest.mock import patch

from scripts.generate_project_dashboard_xlsx import (
    generate_dashboard,
    verify_dashboard_file,
    col_letter,
    determine_cell_style,
    NS,
)
from courier_runtime.workbook import read_cells


def test_col_letter():
    assert col_letter(1) == "A"
    assert col_letter(26) == "Z"
    assert col_letter(27) == "AA"
    assert col_letter(28) == "AB"


def test_determine_cell_style():
    # Header is style 1
    assert determine_cell_style("Header", is_header=True) == 1
    # Success / Done is style 2
    assert determine_cell_style("VERIFIED") == 2
    assert determine_cell_style("SUCCESS") == 2
    # In progress / Pending is style 3
    assert determine_cell_style("IN_PROGRESS") == 3
    # Failed / Error is style 4
    assert determine_cell_style("FAILED") == 4
    # Numeric
    assert determine_cell_style("100", is_num=True) == 6
    # Monospace code
    assert determine_cell_style("abc", is_code=True) == 5


def test_generate_and_verify_dashboard_xlsx(tmp_path):
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    out_file = str(tmp_path / "test_dashboard.xlsx")

    # Mock open PRs if gh CLI fails in offline/restricted CI environments
    mock_prs = [
        {
            "number": 315,
            "title": "[L4] adapter bridge",
            "headRefName": "lane/L4-bridge",
            "author": {"login": "happyhippovip"},
            "statusCheckRollup": [{"conclusion": "SUCCESS"}],
            "mergeable": "MERGEABLE",
            "createdAt": "2026-10-08T10:00:00Z"
        }
    ]

    with patch("scripts.generate_project_dashboard_xlsx.get_open_prs", return_value=mock_prs):
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
