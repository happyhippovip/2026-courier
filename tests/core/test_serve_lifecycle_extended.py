import json
import os
import signal
import threading
import time
import urllib.request
import urllib.error
import pytest
from pathlib import Path
from courier_core.serve import Service, HomeLock, load_or_create_token

def test_home_lock_double_acquire(tmp_path):
    lock1 = HomeLock(tmp_path / "run" / "controller.lock")
    assert lock1.acquire() is True
    lock2 = HomeLock(tmp_path / "run" / "controller.lock")
    assert lock2.acquire() is False
    lock1.release()
    assert lock2.acquire() is True
    lock2.release()

def test_load_or_create_token(tmp_path):
    p = tmp_path / "run" / "controller.token"
    tok1 = load_or_create_token(p)
    assert len(tok1) >= 32
    assert p.is_file()
    # Re-reading should yield identical token
    tok2 = load_or_create_token(p)
    assert tok1 == tok2

def test_service_lifecycle_health_and_shutdown(tmp_path):
    service = Service(tmp_path, port=0)
    port = service.port
    assert port > 0
    token = (tmp_path / "run" / "controller.token").read_text().strip()

    srv_thread = threading.Thread(target=service.run, daemon=True)
    srv_thread.start()

    time.sleep(0.3)
    base_url = f"http://127.0.0.1:{port}"

    # 1. Health without token -> 401
    req = urllib.request.Request(f"{base_url}/v1/health")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
    assert exc_info.value.code == 401

    # 2. Health with token -> 200
    req = urllib.request.Request(f"{base_url}/v1/health", headers={"X-Courier-Token": token})
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert "mode" in data
        assert "head_seq" in data

    # 3. Shutdown via POST /v1/shutdown
    req_stop = urllib.request.Request(
        f"{base_url}/v1/shutdown",
        data=b"{}",
        headers={"X-Courier-Token": token, "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req_stop) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data.get("status") == "STOPPING"

    srv_thread.join(timeout=3.0)
    assert not srv_thread.is_alive()
