import pytest
import os
import sys
import json
import shutil
from unittest import mock
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.windows_update_manager import WindowsUpdateManager

@pytest.fixture
def manager(tmp_path):
    mgr = WindowsUpdateManager()
    mgr.state_file = str(tmp_path / 'central_state.json')
    mgr.backup_dir = str(tmp_path / 'backup_update')
    return mgr, tmp_path

def test_checkpoint_state(manager):
    mgr, tmp = manager
    
    # Create fake files
    Path(mgr.state_file).write_text('{"state": 1}')
    worker_file = tmp / 'worker_state.json'
    worker_file.write_text('{"w": 2}')
    
    # We patch os.path.exists and shutil.copy2 for the non-absolute paths
    with mock.patch("os.path.exists") as mock_exists:
        # custom exists logic
        def side_effect(path):
            if path in [mgr.state_file, str(worker_file), mgr.backup_dir]: return True
            if path == 'worker_state.json': return True # Simulate it existing in cwd
            return False
        mock_exists.side_effect = side_effect
        
        with mock.patch("shutil.copy2") as mock_copy:
            mgr.checkpoint_state()
            
            # Should have called copy for state_file and worker_state.json
            assert mock_copy.call_count == 2
            args_list = [call[0][0] for call in mock_copy.call_args_list]
            assert mgr.state_file in args_list
            assert 'worker_state.json' in args_list

def test_migrate_schema(manager):
    mgr, tmp = manager
    
    # Create state
    Path(mgr.state_file).write_text(json.dumps({"goals": {}}))
    
    mgr.migrate_schema()
    
    # Verify migration
    data = json.loads(Path(mgr.state_file).read_text())
    assert data["schema_version"] == "1.1.0"

def test_run_update_flow_success(manager):
    mgr, tmp = manager
    Path(mgr.state_file).write_text('{"goals": {}}')
    
    # Ensure backup dir doesn't exist initially
    if os.path.exists(mgr.backup_dir):
        shutil.rmtree(mgr.backup_dir)
        
    with mock.patch.object(mgr, 'checkpoint_state') as mock_chk:
        with mock.patch.object(mgr, 'stop_runtime'):
            with mock.patch.object(mgr, 'update_files'):
                with mock.patch.object(mgr, 'migrate_schema'):
                    # To test successful cleanup, we must create the backup dir so rmtree succeeds
                    def mock_chk_effect():
                        os.makedirs(mgr.backup_dir)
                    mock_chk.side_effect = mock_chk_effect
                    
                    mgr.run_update_flow(simulate_failure=False)
                    
    # backup_dir should be deleted
    assert not os.path.exists(mgr.backup_dir)

def test_run_update_flow_failure_rollback(manager):
    mgr, tmp = manager
    Path(mgr.state_file).write_text('{"goals": {}}')
    
    with mock.patch.object(mgr, 'checkpoint_state') as mock_chk:
        with mock.patch.object(mgr, 'stop_runtime'):
            with mock.patch.object(mgr, 'update_files'):
                with mock.patch.object(mgr, 'migrate_schema'):
                    with mock.patch.object(mgr, 'rollback') as mock_rollback:
                        mgr.run_update_flow(simulate_failure=True)
                        
    # backup_dir would normally remain, rollback called
    mock_rollback.assert_called_once()

def test_rollback(manager):
    mgr, tmp = manager
    
    # Create backup dir and a file in it
    os.makedirs(mgr.backup_dir)
    backup_file = os.path.join(mgr.backup_dir, 'account_session.json')
    Path(backup_file).write_text('{"account": "old"}')
    
    with mock.patch("shutil.copy2") as mock_copy:
        mgr.rollback()
        
    mock_copy.assert_called_once_with(backup_file, 'account_session.json')

