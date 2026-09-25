import pytest
import os
import sys
import time
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import log_rotation

def test_rotate_logs_no_dir():
    # Should simply return without error if dir doesn't exist
    with mock.patch("os.path.exists", return_value=False):
        log_rotation.rotate_logs("missing_dir")

def test_rotate_logs_age(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    
    # Create two files: one old, one new
    old_file = log_dir / "old.log"
    new_file = log_dir / "new.log"
    
    old_file.write_text("old")
    new_file.write_text("new")
    
    now = time.time()
    
    # Mock os.stat to return different modification times
    original_stat = os.stat
    def mock_stat(path):
        if "old.log" in str(path):
            mock_st = mock.Mock()
            mock_st.st_mtime = now - (10 * 86400) # 10 days old
            return mock_st
        if "new.log" in str(path):
            mock_st = mock.Mock()
            mock_st.st_mtime = now - (1 * 86400) # 1 day old
            return mock_st
        return original_stat(path)
        
    with mock.patch("os.stat", side_effect=mock_stat):
        with mock.patch("time.time", return_value=now):
            log_rotation.rotate_logs(str(log_dir), max_files=10, max_age_days=7)
            
    assert not old_file.exists()
    assert new_file.exists()

def test_rotate_logs_count(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    
    now = time.time()
    
    # Create 5 files
    files = []
    for i in range(5):
        f = log_dir / f"file_{i}.log"
        f.write_text("test")
        files.append(f)
        
    # Mock os.stat to make file_0 oldest, file_4 newest
    original_stat = os.stat
    def mock_stat(path):
        for i in range(5):
            if f"file_{i}.log" in str(path):
                mock_st = mock.Mock()
                mock_st.st_mtime = now - (5 - i) * 1000 # Older files have smaller timestamps
                return mock_st
        return original_stat(path)
        
    with mock.patch("os.stat", side_effect=mock_stat):
        with mock.patch("time.time", return_value=now):
            log_rotation.rotate_logs(str(log_dir), max_files=3, max_age_days=7)
            
    # files 0 and 1 should be deleted (the oldest 2)
    assert not files[0].exists()
    assert not files[1].exists()
    
    # files 2, 3, and 4 should remain
    assert files[2].exists()
    assert files[3].exists()
    assert files[4].exists()

