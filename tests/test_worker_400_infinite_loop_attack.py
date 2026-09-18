import pytest
import os
import time
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_worker_400_loop():
    import urllib.request
    import json
    
    server_script = """
import socket
import time
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('127.0.0.1', 8089))
s.listen(1)
while True:
    conn, addr = s.accept()
    data = conn.recv(4096)
    if not data: break
    conn.sendall(b"HTTP/1.1 400 Bad Request\\r\\nContent-Type: application/json\\r\\nContent-Length: 22\\r\\n\\r\\n{\\"error\\": \\"bad test\\"}")
    time.sleep(0.1)
    conn.close()
"""
    server_path = Path("/tmp/fake_400_server.py")
    server_path.write_text(server_script)
    
    server_proc = subprocess.Popen([sys.executable, str(server_path)])
    time.sleep(1)
    
    sys.path.append(str(REPO_ROOT / "scripts"))
    from mac_worker.daemon import http_post
    
    config = {"COURIER_SERVER": "http://127.0.0.1:8089", "COURIER_API_KEY": "test"}
    res, err = http_post(config, "/tasks/result", {"bad": "data"})
    
    server_proc.kill()
    
    assert err is not None
    assert "400" in err
    
    with open(REPO_ROOT / "scripts" / "mac_worker" / "daemon.py") as f:
        code = f.read()
        
    assert 'if "409" in err or "404" in err or "400" in err:' in code, "Worker loops forever on 400 Bad Request!"
