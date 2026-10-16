import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
import sys

# Add scripts to path so we can import ci_truth
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.ci_truth import run_ci_truth, generate_dockerfile

def test_generate_dockerfile_requirements(tmp_path):
    (tmp_path / "requirements.txt").write_text("pytest")
    df = generate_dockerfile(tmp_path)
    assert "pip install -r requirements.txt" in df

def test_generate_dockerfile_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text("")
    df = generate_dockerfile(tmp_path)
    assert "pip install ." in df

@patch("subprocess.run")
@patch("subprocess.Popen")
def test_run_ci_truth_success(mock_popen, mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=0, stdout="1 passed", stderr="")
    res = run_ci_truth(str(tmp_path), "HEAD")
    assert res["status"] == "pass"
    assert res["classification"] == "clean"

@patch("subprocess.run")
@patch("subprocess.Popen")
def test_run_ci_truth_env_failure(mock_popen, mock_run, tmp_path):
    # build succeeds, run fails with ModuleNotFoundError
    def side_effect(*args, **kwargs):
        cmd = args[0]
        if cmd[0] == "docker" and cmd[1] == "run":
            return MagicMock(returncode=1, stdout="ModuleNotFoundError: No module named 'requests'", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")
    mock_run.side_effect = side_effect
    
    res = run_ci_truth(str(tmp_path), "HEAD")
    assert res["status"] == "fail"
    assert res["classification"] == "env"

@patch("subprocess.run")
@patch("subprocess.Popen")
def test_run_ci_truth_product_failure(mock_popen, mock_run, tmp_path):
    # build succeeds, run fails with AssertionError
    def side_effect(*args, **kwargs):
        cmd = args[0]
        if cmd[0] == "docker" and cmd[1] == "run":
            return MagicMock(returncode=1, stdout="AssertionError: 1 != 2", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")
    mock_run.side_effect = side_effect
    
    res = run_ci_truth(str(tmp_path), "HEAD")
    assert res["status"] == "fail"
    assert res["classification"] == "product"
