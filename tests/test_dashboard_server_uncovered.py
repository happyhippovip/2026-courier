import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import dashboard.server as d_server

@pytest.fixture
def mock_dirs(tmp_path):
    courier_dir = tmp_path / "2026-courier"
    memory_dir = tmp_path / "2026-project-memory"
    events_dir = courier_dir / "events"
    
    courier_dir.mkdir(parents=True)
    memory_dir.mkdir(parents=True)
    events_dir.mkdir(parents=True)
    
    # Mocking global paths in the dashboard server
    with patch("dashboard.server.COURIER_DIR", courier_dir), \
         patch("dashboard.server.MEMORY_DIR", memory_dir), \
         patch("dashboard.server.EVENTS_DIR", events_dir):
        yield {
            "courier_dir": courier_dir,
            "memory_dir": memory_dir,
            "events_dir": events_dir,
            "tmp_path": tmp_path
        }

def test_get_status_payload_no_files(mock_dirs):
    payload = d_server.get_status_payload()
    assert payload["status"] == "ONLINE"
    assert payload["memory_head"] == "UNKNOWN"
    assert payload["courier_head"] == "UNKNOWN"

def test_get_status_payload_with_files(mock_dirs):
    mem_dir = mock_dirs["memory_dir"]
    courier_dir = mock_dirs["courier_dir"]
    events_dir = mock_dirs["events_dir"]
    
    # Setup .git files
    mem_git = mem_dir / ".git"
    mem_git.mkdir()
    (mem_git / "HEAD").write_text("ref: refs/heads/main")
    (mem_git / "refs" / "heads").mkdir(parents=True)
    (mem_git / "refs" / "heads" / "main").write_text("1234567890")
    
    courier_git = courier_dir / ".git"
    courier_git.mkdir()
    (courier_git / "HEAD").write_text("abcdef1234")
    
    # Setup event files
    (events_dir / "runtime-state").mkdir()
    (events_dir / "runtime-state" / "central_motto.json").write_text('{"motto": "TEST MOTTO"}', encoding="utf-8")
    (events_dir / "runtime-state" / "hq_telemetry_snapshot.json").write_text('{"cpu": 50}', encoding="utf-8")
    
    (events_dir / "worker-registry").mkdir()
    (events_dir / "worker-registry" / "active_workers.json").write_text('{"w1": {}}', encoding="utf-8")
    
    payload = d_server.get_status_payload()
    assert payload["memory_head"] == "1234567"
    assert payload["courier_head"] == "abcdef1"
    assert payload["central_motto"] == "TEST MOTTO"
    assert payload["active_workers_count"] == 1
    assert payload["hq_snapshot"] == {"cpu": 50}

def test_get_ledger_value_payload(mock_dirs):
    events_dir = mock_dirs["events_dir"]
    
    (events_dir / "processed").mkdir()
    (events_dir / "processed" / "task_dedupe_registry.json").write_text('{"t1": {"registered_at": "2026-10-01"}}', encoding="utf-8")
    (events_dir / "processed" / "reuse_events.jsonl").write_text('{"original_task_id": "t1", "timestamp": "2026-10-01", "result_file": "r1.json"}\n', encoding="utf-8")
    (events_dir / "processed" / "result1.json").write_text("{}")
    
    # Mock datetime to always return a specific date
    with patch("dashboard.server._dt") as mock_dt:
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2026-10"
        mock_now.isoformat.return_value = "2026-10-01T00:00:00"
        mock_dt.datetime.now.return_value = mock_now
        
        payload = d_server.get_ledger_value_payload()
        
    assert payload["metrics"]["results_reused"]["value"] == 1
    assert payload["metrics"]["evidence_files_available"]["value"] == 1
    assert payload["this_month"]["work_units_completed"]["value"] == 1
    assert len(payload["evidence"]) == 1

def test_get_commercial_offers_payload(mock_dirs):
    events_dir = mock_dirs["events_dir"]
    
    (events_dir / "revenue-opportunities").mkdir()
    (events_dir / "revenue-opportunities" / "canonical_revenue_ledger.json").write_text('{"opportunities": {"op1": {"title": "Test Opp", "state": "OPEN"}}}', encoding="utf-8")
    
    payload = d_server.get_commercial_offers_payload()
    assert payload["total_offers"] == 1
    assert payload["offers"][0]["opportunity_id"] == "op1"
    assert payload["offers"][0]["title"] == "Test Opp"

def setup_handler(path):
    handler = d_server.CommandCenterHandler.__new__(d_server.CommandCenterHandler)
    handler.path = path
    import io
    handler.wfile = io.BytesIO()
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    return handler

def test_handler_api_status(mock_dirs):
    handler = setup_handler("/api/status")
    handler.do_GET()
    resp = json.loads(handler.wfile.getvalue().decode("utf-8"))
    assert resp["status"] == "ONLINE"

def test_handler_api_ledger(mock_dirs):
    handler = setup_handler("/api/ledger-value")
    handler.do_GET()
    resp = json.loads(handler.wfile.getvalue().decode("utf-8"))
    assert "metrics" in resp

def test_handler_api_offers(mock_dirs):
    handler = setup_handler("/api/offers")
    handler.do_GET()
    resp = json.loads(handler.wfile.getvalue().decode("utf-8"))
    assert "total_offers" in resp

def test_handler_fallback(mock_dirs):
    handler = setup_handler("/invalid")
    with patch("http.server.SimpleHTTPRequestHandler.do_GET") as mock_super:
        handler.do_GET()
        mock_super.assert_called_once()

def test_exceptions_in_payloads(mock_dirs):
    # Test that exceptions during file reads don't crash the server
    events_dir = mock_dirs["events_dir"]
    
    (events_dir / "runtime-state").mkdir()
    (events_dir / "runtime-state" / "central_motto.json").write_text('invalid json')
    (events_dir / "runtime-state" / "hq_telemetry_snapshot.json").write_text('invalid json')
    
    (events_dir / "worker-registry").mkdir()
    (events_dir / "worker-registry" / "active_workers.json").write_text('invalid json')
    
    (events_dir / "processed").mkdir()
    (events_dir / "processed" / "task_dedupe_registry.json").write_text('invalid json')
    (events_dir / "processed" / "reuse_events.jsonl").write_text('invalid json')
    
    (events_dir / "revenue-opportunities").mkdir()
    (events_dir / "revenue-opportunities" / "canonical_revenue_ledger.json").write_text('invalid json')
    
    mem_dir = mock_dirs["memory_dir"]
    courier_dir = mock_dirs["courier_dir"]
    
    mem_git = mem_dir / ".git"
    mem_git.mkdir()
    (mem_git / "HEAD").mkdir() # causes exception when read
    
    courier_git = courier_dir / ".git"
    courier_git.mkdir()
    (courier_git / "HEAD").mkdir() # causes exception when read
    
    # Should not raise
    d_server.get_status_payload()
    d_server.get_ledger_value_payload()
    d_server.get_commercial_offers_payload()

def test_courier_commit_ref_path(mock_dirs):
    # Test valid courier commit ref path
    courier_dir = mock_dirs["courier_dir"]
    courier_git = courier_dir / ".git"
    courier_git.mkdir()
    (courier_git / "HEAD").write_text("ref: refs/heads/main")
    (courier_git / "refs" / "heads").mkdir(parents=True)
    (courier_git / "refs" / "heads" / "main").write_text("abcdef1234")
    
    payload = d_server.get_status_payload()
    assert payload["courier_head"] == "abcdef1"

def test_main_startup_retry():
    with patch("socketserver.TCPServer") as mock_tcp:
        # Simulate Address in use on first call, success on second
        mock_instance = MagicMock()
        mock_tcp.side_effect = [OSError("Address already in use"), mock_instance]
        mock_instance.__enter__.return_value = mock_instance
        
        d_server.main()
        mock_instance.serve_forever.assert_called_once()

class MockServer:
    def __init__(self):
        self.server_address = ("127.0.0.1", 8080)

def test_create_server():
    # Only test that the server can be created.
    with patch("socketserver.TCPServer"):
        server = d_server.create_server(12345)
        assert server is not None

def test_main_startup():
    with patch("socketserver.TCPServer") as mock_tcp:
        mock_instance = MagicMock()
        mock_tcp.return_value.__enter__.return_value = mock_instance
        d_server.main()
        mock_instance.serve_forever.assert_called_once()
