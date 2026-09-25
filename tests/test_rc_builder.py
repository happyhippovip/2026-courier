import pytest
import os
import sys
import json
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import rc_builder

def test_build_release_candidate_success(tmp_path):
    # Change working dir so rc_report.json goes to tmp_path
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        def mock_exists(path):
            if "first_run.py" in path: return True
            if "revenue_customer_intake.py" in path: return True
            if "human_gate_ux.py" in path: return True
            return False
            
        with mock.patch("os.path.exists", side_effect=mock_exists):
            with mock.patch("subprocess.check_output", return_value=b"mocked_sha\n"):
                rc_builder.build_release_candidate()
                
        report_file = tmp_path / "rc_report.json"
        assert report_file.exists()
        
        report = json.loads(report_file.read_text())
        assert report["RELEASE_CANDIDATE"] == "PASS"
        assert report["SHA"] == "mocked_sha"
        assert report["WINDOWS_READY"] is True
        assert report["REVENUE_V1_READY"] is True
        assert report["CUSTOMER_READY"] == "YES"
        assert report["BLOCKER"] == "NONE"
    finally:
        os.chdir(original_cwd)

def test_build_release_candidate_missing_components(tmp_path):
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    try:
        def mock_exists(path):
            if "first_run.py" in path: return False
            if "revenue_customer_intake.py" in path: return True
            if "human_gate_ux.py" in path: return True
            return False
            
        with mock.patch("os.path.exists", side_effect=mock_exists):
            with mock.patch("subprocess.check_output", side_effect=Exception("git not found")):
                rc_builder.build_release_candidate()
                
        report_file = tmp_path / "rc_report.json"
        assert report_file.exists()
        
        report = json.loads(report_file.read_text())
        assert report["SHA"] == "unknown"
        assert report["WINDOWS_READY"] is False
        assert report["CUSTOMER_READY"] == "NO"
        assert report["BLOCKER"] == "MISSING_COMPONENTS"
    finally:
        os.chdir(original_cwd)

