import threading
import time
from pathlib import Path
import requests
from courier_hub.server import HubServer, Hub

def test_hub_independent_startup_and_shutdown(tmp_path):
    hub = Hub(Path(tmp_path), "http://127.0.0.1:9999")
    server = HubServer(hub, 0)
    
    # Start hub independently
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1})
    thread.start()
    
    try:
        # Verify startup (alive and answering)
        resp = requests.get(server.url)
        assert resp.status_code == 200
        assert "Courier" in resp.text
    finally:
        # Verify independent shutdown
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive(), "Hub thread failed to shut down within timeout"

