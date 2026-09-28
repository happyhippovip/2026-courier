import pytest
from unittest.mock import Mock, patch
from scripts.courier_verifier import fetch_artifact, MAX_ARTIFACT_BYTES
import requests

def test_fetch_artifact_oom_prevention():
    # Test early rejection by metadata size
    mock_meta_resp = Mock()
    mock_meta_resp.json.return_value = {"size": MAX_ARTIFACT_BYTES + 1}
    mock_blob_resp = Mock()
    
    with patch("requests.get", side_effect=[mock_meta_resp, mock_blob_resp]):
        with pytest.raises(ValueError, match="artifact exceeds size limit"):
            fetch_artifact("art-123")

    # Test chunked reading limit
    mock_meta_resp2 = Mock()
    mock_meta_resp2.json.return_value = {"size": MAX_ARTIFACT_BYTES - 100} # Fake safe meta size to bypass first check
    
    mock_blob_resp2 = Mock()
    # Mock iter_content to yield chunks that exceed limit
    mock_blob_resp2.iter_content.return_value = [b"a" * 8192] * ((MAX_ARTIFACT_BYTES // 8192) + 2)
    
    with patch("requests.get", side_effect=[mock_meta_resp2, mock_blob_resp2]):
        with pytest.raises(ValueError, match="artifact exceeds size limit"):
            fetch_artifact("art-123")
