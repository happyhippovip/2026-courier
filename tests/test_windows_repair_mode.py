import pytest
import os
import sys
import json
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.windows_repair_mode import WindowsRepairUtility

@pytest.fixture
def util(tmp_path):
    u = WindowsRepairUtility()
    u.state_file = str(tmp_path / "central_state.json")
    u.worker_state_file = str(tmp_path / "worker_state.json")
    u.env_file = str(tmp_path / ".env.txt")
    return u, tmp_path

def test_check_credential_access(util, capsys):
    u, tmp = util
    
    u.check_credential_access()
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    
    Path = type(tmp)
    Path(u.env_file).write_text("API_KEY=123")
    u.check_credential_access()
    captured = capsys.readouterr()
    assert "PASS" in captured.out

def test_check_state_schema(util, capsys):
    u, tmp = util
    Path = type(tmp)
    
    # Missing
    u.check_state_schema()
    
    # Invalid JSON
    Path(u.state_file).write_text("{bad")
    u.check_state_schema()
    captured = capsys.readouterr()
    assert "State corrupted" in captured.out
    
    # Missing goals
    Path(u.state_file).write_text("{}")
    u.check_state_schema()
    captured = capsys.readouterr()
    assert "Malformed schema" in captured.out
    
    # Valid
    Path(u.state_file).write_text('{"goals": {}}')
    u.check_state_schema()
    captured = capsys.readouterr()
    assert "Schema is valid" in captured.out

def test_clean_orphaned_executions(util, capsys):
    u, tmp = util
    Path = type(tmp)
    
    Path(u.worker_state_file).write_text(json.dumps({"owned_pids": [99999]}))
    
    with mock.patch("psutil.Process") as mock_process:
        # Simulate NoSuchProcess
        import psutil
        mock_process.side_effect = psutil.NoSuchProcess(99999)
        u.clean_orphaned_executions()
        
    wstate = json.loads(Path(u.worker_state_file).read_text())
    assert wstate["owned_pids"] == []
    
    Path(u.worker_state_file).write_text(json.dumps({"owned_pids": [1000]}))
    with mock.patch("psutil.Process") as mock_process:
        mock_p = mock.Mock()
        mock_child = mock.Mock()
        mock_p.children.return_value = [mock_child]
        mock_process.return_value = mock_p
        
        u.clean_orphaned_executions()
        
        mock_child.terminate.assert_called_once()
        mock_p.terminate.assert_called_once()
        
    wstate = json.loads(Path(u.worker_state_file).read_text())
    assert wstate["owned_pids"] == []

def test_run(util):
    u, tmp = util
    with mock.patch.object(u, 'check_credential_access') as m1, \
         mock.patch.object(u, 'check_state_schema') as m2, \
         mock.patch.object(u, 'check_worker_registration') as m3, \
         mock.patch.object(u, 'remove_stale_ui_handles') as m4, \
         mock.patch.object(u, 'clean_orphaned_executions') as m5, \
         mock.patch.object(u, 'run_health_check') as m6, \
         mock.patch.object(u, 'restart_exact_courier_runtime') as m7:
         
         u.run()
         
         m1.assert_called_once()
         m7.assert_called_once()

