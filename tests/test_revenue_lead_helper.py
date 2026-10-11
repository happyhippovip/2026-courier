import os
import sys
from unittest.mock import patch, MagicMock

import pytest

from scripts.revenue_lead_helper import run_lead_helper

def test_run_lead_helper(tmp_path):
    workbook_path = tmp_path / "test_messy_leads.xlsx"
    workbook_path.touch()
    
    mock_cells = {
        "A1": "Name", "B1": "Email", "C1": "Phone",
        "A2": "JOHN DOE", "B2": "   JOHN.DOE@Example.com   ", "C2": "555-1234",
        "A3": "Jane Smith", "B3": "jane.smith@EXAMPLE.ORG", "C3": "555-5678",
        "A4": "Bob", "B4": "CONTACT: bob@company.net!!", "C4": "1234567890"
    }
    
    with patch("scripts.revenue_lead_helper.read_cells", return_value=mock_cells):
        leads = run_lead_helper(str(workbook_path))
        
    assert len(leads) == 3
    assert leads[0].organisation == "JOHN DOE"
    assert leads[0].lead_id == "L-2"
    assert leads[0].state == "PROSPECT"
    
    assert leads[1].organisation == "Jane Smith"
    assert leads[1].lead_id == "L-3"
    
    assert leads[2].organisation == "Bob"
    assert leads[2].lead_id == "L-4"

def test_run_lead_helper_missing_file(capsys):
    with pytest.raises(SystemExit) as e:
        run_lead_helper("nonexistent.xlsx")
    assert e.value.code == 1
    out, err = capsys.readouterr()
    assert "not found" in out
