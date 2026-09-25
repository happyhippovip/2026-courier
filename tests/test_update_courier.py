import os
import sys
from unittest import mock
import zipfile

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import update_courier

def test_get_current_version(tmp_path):
    assert update_courier.get_current_version(str(tmp_path)) == "1.0.0"
    
    version_file = tmp_path / "version.txt"
    version_file.write_text("1.5.0")
    assert update_courier.get_current_version(str(tmp_path)) == "1.5.0"

def test_get_update_version(tmp_path):
    assert update_courier.get_update_version(str(tmp_path)) == "UNKNOWN"
    
    version_file = tmp_path / "version.txt"
    version_file.write_text("2.0.0")
    assert update_courier.get_update_version(str(tmp_path)) == "2.0.0"

def test_restart_service():
    with mock.patch("platform.system", return_value="Windows"):
        with mock.patch("scripts.update_courier.run_command") as mock_run:
            with mock.patch("time.sleep"):
                update_courier.restart_service()
                assert mock_run.call_count == 2
                
    with mock.patch("platform.system", return_value="Linux"):
        with mock.patch("scripts.update_courier.run_command") as mock_run:
            update_courier.restart_service()
            mock_run.assert_called_once_with(["systemctl", "restart", "courier"])

def test_health_check(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    hc_script = scripts_dir / "product_health_check.py"
    hc_script.touch()
    
    mock_res = mock.Mock()
    mock_res.returncode = 0
    mock_res.stdout = b"HEALTHY"
    
    with mock.patch("scripts.update_courier.run_command", return_value=mock_res):
        assert update_courier.health_check(str(tmp_path)) == True
        
    mock_res.stdout = b"DEGRADED"
    with mock.patch("scripts.update_courier.run_command", return_value=mock_res):
        assert update_courier.health_check(str(tmp_path)) == False

@mock.patch("scripts.update_courier.get_current_version", return_value="1.0.0")
@mock.patch("scripts.update_courier.get_update_version", return_value="2.0.0")
@mock.patch("shutil.copytree")
@mock.patch("shutil.copy2")
@mock.patch("scripts.update_courier.restart_service")
@mock.patch("scripts.update_courier.health_check", return_value=True)
def test_main_success(mock_hc, mock_restart, mock_copy2, mock_copytree, mock_guv, mock_gcv, tmp_path):
    # Create fake update zip
    zip_path = tmp_path / "update.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr('file.txt', 'data')
        
    with mock.patch.object(sys, 'argv', ['update_courier.py', str(zip_path)]):
        with mock.patch("scripts.update_courier.run_command") as mock_run:
            mock_res = mock.Mock()
            mock_res.returncode = 0
            mock_run.return_value = mock_res
            
            with mock.patch("time.sleep"):
                update_courier.main()
                
    mock_hc.assert_called_once()
    mock_restart.assert_called_once()

