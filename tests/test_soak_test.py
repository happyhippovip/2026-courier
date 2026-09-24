import http.server
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


class MockCourierServerHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Quiet logging

    def do_POST(self):
        if self.path == "/goals":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"goal_id": "mock-soak-goal", "status": "PENDING"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "HEALTHY", "active_goals": 1}).encode())
        else:
            self.send_response(404)
            self.end_headers()


def test_soak_test_execution_with_mock_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), MockCourierServerHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        env = os.environ.copy()
        env["COURIER_SERVER"] = f"http://127.0.0.1:{port}"
        env["COURIER_API_KEY"] = "mock-key"
        env["COURIER_SOAK_COUNT"] = "2"
        env["COURIER_SOAK_DELAY"] = "0"
        env["COURIER_SOAK_DURATION"] = "0"

        script_path = REPO_ROOT / "tests" / "acceptance" / "soak_test.py"
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )

        assert proc.returncode == 0
        assert "Starting Soak Test..." in proc.stdout
        assert "Submitted 2 goals." in proc.stdout
        assert "Soak test complete." in proc.stdout
    finally:
        server.shutdown()
        server.server_close()
