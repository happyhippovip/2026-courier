from pathlib import Path
import json
import pytest
from unittest.mock import patch, MagicMock

from scripts.lead_research_helper import find_ci_pain_leads
from courier_runtime.revenue import QUALIFIED
from courier_runtime.revenue_store import RevenueStore


def test_find_ci_pain_leads_success(tmp_path):
    fake_issues = [
        {
            "repository": {"nameWithOwner": "testorg/testrepo"},
            "url": "https://github.com/testorg/testrepo/issues/42",
            "title": "CI test failure",
            "body": "ModuleNotFoundError: No module named 'foo'",
        },
        {
            "repository": {"nameWithOwner": "anotherorg/otherrepo"},
            "url": "https://github.com/anotherorg/otherrepo/issues/100",
            "title": "Assert failed",
            "body": "AssertionError: expected true got false",
        },
    ]

    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = json.dumps(fake_issues)

    with patch("subprocess.run", mock_run):
        find_ci_pain_leads(str(tmp_path))

    store = RevenueStore(str(tmp_path))
    leads = store.leads()
    assert len(leads) == 2
    assert leads[0].organisation == "testorg"
    assert "ModuleNotFoundError" in leads[0].problem
    assert leads[0].state == QUALIFIED
    assert leads[1].organisation == "anotherorg"
    assert "AssertionError" in leads[1].problem


def test_find_ci_pain_leads_subprocess_failure(tmp_path, capsys):
    mock_run = MagicMock()
    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = "API rate limit exceeded"

    with patch("subprocess.run", mock_run):
        find_ci_pain_leads(str(tmp_path))

    captured = capsys.readouterr()
    assert "Search failed" in captured.out

    store = RevenueStore(str(tmp_path))
    assert len(store.leads()) == 0
