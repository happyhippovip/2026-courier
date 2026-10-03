import pytest
import requests
from tests.controller.test_ctrl_service import LiveService

def test_authenticated_health_contract(tmp_path):
    # Spin up controller
    home = tmp_path / "home"
    live = LiveService(home)
    
    try:
        url = live.base + "/v1/health"
        
        # 1. Prove 401 without token
        resp_unauth = requests.get(url, timeout=2)
        assert resp_unauth.status_code == 401, "Health check unexpectedly allowed without token!"
        
        # 2. Prove 401 with invalid token
        resp_bad = requests.get(url, headers={"X-Courier-Token": "bad_token"}, timeout=2)
        assert resp_bad.status_code == 401, "Health check unexpectedly allowed with invalid token!"
        
        # 3. Prove success with valid token
        resp_auth = requests.get(url, headers={"X-Courier-Token": live.service.token}, timeout=2)
        assert resp_auth.status_code == 200, "Health check rejected valid token!"
        
        # Ensure it returns valid JSON health payload
        data = resp_auth.json()
        assert "mode" in data
        assert "head_seq" in data
        
    finally:
        live.stop()

