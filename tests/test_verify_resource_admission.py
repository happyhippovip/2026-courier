import sys
import os
import pytest
import psutil
from unittest.mock import patch, MagicMock
from pathlib import Path
import runpy

def run_script():
    repo_root = str(Path(__file__).resolve().parent.parent)
    script_path = Path(repo_root) / "scripts" / "verify_resource_admission.py"
    
    with patch("sys.exit", side_effect=SystemExit) as m_exit:
        try:
            runpy.run_path(str(script_path), run_name="__main__")
        except SystemExit:
            pass
        return m_exit

@pytest.fixture
def mock_psutil_clean():
    mock_mem = MagicMock()
    mock_mem.available = 1024 * 1024 * 2048 # 2048 MB
    
    mock_disk = MagicMock()
    mock_disk.free = 1024 * 1024 * 2048 # 2048 MB

    patchers = [
        patch("psutil.cpu_percent", return_value=10.0),
        patch("psutil.virtual_memory", return_value=mock_mem),
        patch("psutil.disk_usage", return_value=mock_disk)
    ]
    
    for p in patchers:
        p.start()
        
    yield
    
    for p in patchers:
        p.stop()

def test_verify_resource_admission_success(capsys, mock_psutil_clean):
    m_exit = run_script()
    captured = capsys.readouterr()
    assert "RESOURCE ADMISSION VALID: Host is ready for heavy jobs." in captured.out
    m_exit.assert_called_once_with(0)

def test_verify_resource_admission_cpu_high(capsys, mock_psutil_clean):
    with patch("psutil.cpu_percent", return_value=90.0):
        m_exit = run_script()
        
    captured = capsys.readouterr()
    assert "CPU is too busy: 90.0% used." in captured.out
    m_exit.assert_called_once_with(1)

def test_verify_resource_admission_ram_low(capsys, mock_psutil_clean):
    mock_mem = MagicMock()
    mock_mem.available = 1024 * 1024 * 256 # 256 MB
    with patch("psutil.virtual_memory", return_value=mock_mem):
        m_exit = run_script()
        
    captured = capsys.readouterr()
    assert "Not enough RAM available: 256.00 MB" in captured.out
    m_exit.assert_called_once_with(1)

def test_verify_resource_admission_disk_low(capsys, mock_psutil_clean):
    mock_disk = MagicMock()
    mock_disk.free = 1024 * 1024 * 512 # 512 MB
    with patch("psutil.disk_usage", return_value=mock_disk):
        m_exit = run_script()
        
    captured = capsys.readouterr()
    assert "Not enough Disk space: 512.00 MB" in captured.out
    m_exit.assert_called_once_with(1)
