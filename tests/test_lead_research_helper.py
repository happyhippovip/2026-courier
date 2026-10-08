import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.lead_research_helper import find_ci_pain_leads
from courier_runtime.revenue_store import RevenueStore


def test_find_ci_pain_leads_success(tmp_path):
    mock_gh_output = json.dumps([
        {
            "repository": {"nameWithOwner": "octocat/hello-world"},
            "url": "https://github.com/octocat/hello-world/issues/42",
            "title": "Build broken on Python 3.11",
            "body": "Running pytest gave ModuleNotFoundError: No module named 'requests'"
        },
        {
            "repository": {"nameWithOwner": "acme/corp-tools"},
            "url": "https://github.com/acme/corp-tools/issues/100",
            "title": "Test failure in core suite",
            "body": "E AssertionError: assert 1 == 2"
        },
        {
            "repository": {"nameWithOwner": "open-source/project"},
            "url": "https://github.com/open-source/project/issues/999",
            "title": "Random pipeline crash",
            "body": "Exit code 137 OOM killed"
        }
    ])

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = mock_gh_output
    mock_process.stderr = ""

    with patch("subprocess.run", return_value=mock_process) as mock_run:
        find_ci_pain_leads(str(tmp_path))

    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert cmd[:3] == ["gh", "search", "issues"]

    store = RevenueStore(str(tmp_path))
    leads = store.leads()
    assert len(leads) == 3

    # Lead 1: ModuleNotFoundError
    lead1 = leads[0]
    assert lead1.organisation == "octocat"
    assert lead1.source == "https://github.com/octocat/hello-world/issues/42"
    assert "Environment dependency missing (ModuleNotFoundError)." in lead1.problem
    assert lead1.state == "QUALIFIED"
    assert len(lead1.history) == 1

    # Lead 2: AssertionError
    lead2 = leads[1]
    assert lead2.organisation == "acme"
    assert "Product tests failing (AssertionError)." in lead2.problem

    # Lead 3: General failure
    lead3 = leads[2]
    assert lead3.organisation == "open-source"
    assert "General CI failure reported." in lead3.problem


def test_find_ci_pain_leads_search_failure(tmp_path, capsys):
    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.stdout = ""
    mock_process.stderr = "Authentication required"

    with patch("subprocess.run", return_value=mock_process):
        find_ci_pain_leads(str(tmp_path))

    out, err = capsys.readouterr()
    assert "Search failed" in out

    store = RevenueStore(str(tmp_path))
    assert len(store.leads()) == 0


def test_find_ci_pain_leads_empty_results(tmp_path):
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = "[]"
    mock_process.stderr = ""

    with patch("subprocess.run", return_value=mock_process):
        find_ci_pain_leads(str(tmp_path))

    store = RevenueStore(str(tmp_path))
    assert len(store.leads()) == 0
