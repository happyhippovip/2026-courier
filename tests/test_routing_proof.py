import sys
from unittest.mock import patch, MagicMock
import pytest
import runpy
import scripts.routing_proof

def test_routing_proof_success():
    with patch("subprocess.Popen") as mock_popen, \
         patch("time.sleep") as mock_sleep, \
         patch("urllib.request.urlopen") as mock_urlopen:
         
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc
        
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"success": true}'
        mock_resp.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        
        with patch.dict("os.environ", {}):
            runpy.run_path("scripts/routing_proof.py")
        
        assert mock_popen.called
        assert mock_proc.terminate.called
        assert mock_urlopen.call_count == 6
        
def test_routing_proof_http_exception(capsys):
    with patch("subprocess.Popen") as mock_popen, \
         patch("time.sleep") as mock_sleep, \
         patch("urllib.request.urlopen", side_effect=Exception("Mock HTTP Error")) as mock_urlopen:
         
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc
        
        with patch.dict("os.environ", {}):
            runpy.run_path("scripts/routing_proof.py")
            
        assert mock_popen.called
        assert mock_proc.terminate.called
        assert mock_urlopen.call_count == 6
        
        captured = capsys.readouterr()
        assert "Error /workers/register: Mock HTTP Error" in captured.out
