"""Unit and integration tests for Courier V139 Mission Chip."""

import pytest
from pathlib import Path
from courier_hub.mission_chip import run_mission_chip
from courier_hub.server import Hub, HubServer
from urllib.request import Request, urlopen
import json
import threading


def test_mission_chip_deterministic_execution(tmp_path):
    res = run_mission_chip(tmp_path)
    
    assert res["overall_status"] == "COMPLETE"
    assert res["cost_eur"] == 0.00
    assert res["mode"] == "DEMO / LOKAL DETERMINISTISCH"
    assert res["product_ready"] is False
    
    # 3 checks
    checks = res["checks"]
    assert len(checks) == 3
    assert checks[0]["name"] == "Eingabe & Budget-Gate" and checks[0]["passed"] is True
    assert checks[1]["name"] == "Deterministische Ausführung" and checks[1]["passed"] is True
    assert checks[2]["name"] == "Unabhängige Verifikation & Journal-Beleg" and checks[2]["passed"] is True
    
    # Verifier result
    verdict = res["verifier_result"]
    assert verdict["accepted"] is True
    assert verdict["resolution"] == "verified"
    assert verdict["accepted_result_id"] == "res-chip-v139-01"
    assert len(verdict["artifact_sha256"]) == 64
    
    # Events replay
    events = res["events_replay"]
    assert len(events) >= 7
    event_types = [e["type"] for e in events]
    assert "CONTROLLER_STARTED" in event_types
    assert "TASK_CREATED" in event_types
    assert "TASK_CLAIMED" in event_types
    assert "TASK_STARTED" in event_types
    assert "RESULT_READY" in event_types
    assert "RESULT_ACCEPTED" in event_types
    assert "TASK_COMPLETE" in event_types


def test_mission_chip_http_endpoint(tmp_path):
    hub = Hub(tmp_path, "http://127.0.0.1:9999")
    server = HubServer(hub, 0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    
    try:
        base = f"http://127.0.0.1:{port}"
        
        # Test API
        req = Request(f"{base}/hub/api/mission-chip")
        with urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert data["overall_status"] == "COMPLETE"
            assert data["cost_eur"] == 0.00
            assert len(data["checks"]) == 3
            
        # Test static page
        req_page = Request(f"{base}/mission-chip")
        with urlopen(req_page, timeout=5) as resp:
            assert resp.status == 200
            html = resp.read().decode()
            assert "Courier Mission Chip" in html
            assert "Mission starten" in html
            assert "Live-Replay" in html
    finally:
        server.shutdown()
        server.server_close()


def test_mission_chip_cli(tmp_path, capsys):
    from courier_hub.mission_chip import main
    exit_code = main(["--home", str(tmp_path), "--json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["overall_status"] == "COMPLETE"
    assert data["verifier_result"]["resolution"] == "verified"


def test_chip_verifier_rejects_tampered_hash(tmp_path):
    from courier_hub.mission_chip import _chip_verifier
    from types import SimpleNamespace
    
    verifier = _chip_verifier("synthetic")
    task = {"task_id": "t1"}
    # Bad hash
    result = SimpleNamespace(payload={
        "artifacts": [{"path": "mission_result.txt", "sha256": "0000000000000000000000000000000000000000000000000000000000000000", "size_bytes": 34}]
    })
    verdict = verifier(task, result, tmp_path)
    assert verdict.accepted is False
    assert "Gold-Referenz" in verdict.reason


def test_chip_verifier_rejects_tampered_file_bytes(tmp_path):
    from courier_hub.mission_chip import _chip_verifier, EXPECTED_GOLD_SHA256
    from types import SimpleNamespace
    
    # File with manipulated content
    tampered_file = tmp_path / "mission_result.txt"
    tampered_file.write_bytes(b"TAMPERED_BYTES_FORGED")
    
    verifier = _chip_verifier("synthetic")
    task = {"task_id": "t2"}
    # Claimed correct hash but actual file bytes on disk are tampered
    result = SimpleNamespace(payload={
        "artifacts": [{"path": "mission_result.txt", "sha256": EXPECTED_GOLD_SHA256, "size_bytes": 34}]
    })
    verdict = verifier(task, result, tmp_path)
    assert verdict.accepted is False
    assert "Artefakt-Bytes" in verdict.reason


def test_chip_verifier_rejects_missing_artifacts(tmp_path):
    from courier_hub.mission_chip import _chip_verifier
    from types import SimpleNamespace
    
    verifier = _chip_verifier("synthetic")
    task = {"task_id": "t3"}
    # Missing artifacts list
    result = SimpleNamespace(payload={})
    verdict = verifier(task, result, tmp_path)
    assert verdict.accepted is False
    assert "Artefakt fehlt" in verdict.reason


def test_chip_verifier_rejects_gold_sha_without_file(tmp_path):
    from courier_hub.mission_chip import EXPECTED_GOLD_SHA256, _chip_verifier
    from types import SimpleNamespace

    verifier = _chip_verifier("synthetic")
    result = SimpleNamespace(payload={
        "artifacts": [{
            "path": "mission_result.txt",
            "sha256": EXPECTED_GOLD_SHA256,
            "size_bytes": 34,
        }]
    })
    verdict = verifier({"task_id": "t-missing"}, result, tmp_path)
    assert verdict.accepted is False
    assert "fehlt" in verdict.reason


def test_chip_verifier_rejects_path_escape(tmp_path):
    from courier_hub.mission_chip import EXPECTED_GOLD_BYTES, EXPECTED_GOLD_SHA256, _chip_verifier
    from types import SimpleNamespace

    home = tmp_path / "home"
    home.mkdir()
    outside = tmp_path / "mission_escape.txt"
    outside.write_bytes(EXPECTED_GOLD_BYTES)
    verifier = _chip_verifier("synthetic")
    result = SimpleNamespace(payload={
        "artifacts": [{
            "path": "../mission_escape.txt",
            "sha256": EXPECTED_GOLD_SHA256,
            "size_bytes": len(EXPECTED_GOLD_BYTES),
        }]
    })
    verdict = verifier({"task_id": "t-escape"}, result, home)
    assert verdict.accepted is False
    assert "verlässt" in verdict.reason


def test_chip_verifier_rejects_invalid_sha_format(tmp_path):
    from courier_hub.mission_chip import _chip_verifier
    from types import SimpleNamespace
    
    verifier = _chip_verifier("synthetic")
    task = {"task_id": "t4"}
    # Invalid sha format
    result = SimpleNamespace(payload={
        "artifacts": [{"path": "mission_result.txt", "sha256": "bad-short-sha", "size_bytes": 34}]
    })
    verdict = verifier(task, result, tmp_path)
    assert verdict.accepted is False
    assert "Ungültiges SHA-256 Format" in verdict.reason


def test_mission_chip_cli_pretty_output(tmp_path, capsys):
    from courier_hub.mission_chip import main
    # Run CLI without --json
    exit_code = main(["--home", str(tmp_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "COURIER MISSION CHIP" in captured.out
    assert "ERSTE GRÜNE MISSION" in captured.out
    assert "BYTE_LEVEL_GOLD_VERIFIED" or "verified" in captured.out

