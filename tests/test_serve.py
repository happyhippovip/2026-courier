"""Tests for courier_core.serve (Item P9 test hardening).

Covers:
- HomeLock lifecycle and exclusivity
- Token creation, persistence, and recovery
- Route regexes and validation
- Event JSON serialization
- Argument parsing
- In-process HTTP request handling (auth, health, tasks, error codes, shutdown)
"""

from __future__ import annotations

import json
import os
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

import pytest

from courier_core.events import Event, EventType
from courier_core.serve import (
    MAX_BODY_BYTES,
    MAX_EVENT_STREAMS,
    TOKEN_HEADER,
    HomeLock,
    Service,
    _CANCEL_PATH,
    _RESOLVE_PATH,
    _TASK_PATH,
    _event_json,
    load_or_create_token,
    main,
)


# -----------------------------------------------------------------------------
# HomeLock Tests
# -----------------------------------------------------------------------------

def test_home_lock_acquire_and_release(tmp_path: Path):
    lock_path = tmp_path / "run" / "controller.lock"
    lock1 = HomeLock(lock_path)
    assert lock1.acquire() is True
    assert lock_path.exists()

    # Second acquire fails while held
    lock2 = HomeLock(lock_path)
    assert lock2.acquire() is False

    # Release allows re-acquiring
    lock1.release()
    assert lock2.acquire() is True
    lock2.release()


def test_home_lock_double_release_safe(tmp_path: Path):
    lock_path = tmp_path / "run" / "controller.lock"
    lock = HomeLock(lock_path)
    assert lock.acquire() is True
    lock.release()
    # Double release should not raise
    lock.release()


# -----------------------------------------------------------------------------
# Token Management Tests
# -----------------------------------------------------------------------------

def test_load_or_create_token_generates_valid_token(tmp_path: Path):
    token_file = tmp_path / "run" / "controller.token"
    token1 = load_or_create_token(token_file)
    assert isinstance(token1, str)
    assert len(token1) >= 32
    assert token_file.exists()

    # Subsequent load reuses the exact same token
    token2 = load_or_create_token(token_file)
    assert token2 == token1


def test_load_or_create_token_replaces_short_corrupt_token(tmp_path: Path):
    token_file = tmp_path / "run" / "controller.token"
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text("too_short\n", encoding="utf-8")

    token = load_or_create_token(token_file)
    assert len(token) >= 32
    assert token != "too_short"


def test_load_or_create_token_strips_whitespace(tmp_path: Path):
    token_file = tmp_path / "run" / "controller.token"
    token_file.parent.mkdir(parents=True, exist_ok=True)
    clean_token = "a" * 36
    token_file.write_text(f"  {clean_token}  \n", encoding="utf-8")

    loaded = load_or_create_token(token_file)
    assert loaded == clean_token


# -----------------------------------------------------------------------------
# Route Path Regex Tests
# -----------------------------------------------------------------------------

def test_task_path_regex():
    assert _TASK_PATH.match("/v1/tasks/task-1")
    assert _TASK_PATH.match("/v1/tasks/T_123.abc:xyz")
    assert _TASK_PATH.match("/v1/tasks/" + "a" * 200)

    # Invalid paths
    assert not _TASK_PATH.match("/v1/tasks/")
    assert not _TASK_PATH.match("/v1/tasks/foo/bar")
    assert not _TASK_PATH.match("/v1/tasks/has$special")
    assert not _TASK_PATH.match("/v1/tasks/" + "a" * 201)
    assert not _TASK_PATH.match("/v2/tasks/task-1")


def test_cancel_path_regex():
    m = _CANCEL_PATH.match("/v1/tasks/task-001/cancel")
    assert m is not None
    assert m.group(1) == "task-001"

    assert not _CANCEL_PATH.match("/v1/tasks//cancel")
    assert not _CANCEL_PATH.match("/v1/tasks/task-001/cancel/extra")


def test_resolve_path_regex():
    m = _RESOLVE_PATH.match("/v1/tasks/task-999/resolve")
    assert m is not None
    assert m.group(1) == "task-999"

    assert not _RESOLVE_PATH.match("/v1/tasks//resolve")
    assert not _RESOLVE_PATH.match("/v1/tasks/task-999/resolve/more")


# -----------------------------------------------------------------------------
# Event JSON Helper Tests
# -----------------------------------------------------------------------------

def test_event_json_serialization():
    payload = {
        "adapter": "synthetic",
        "params": {"duration_ms": 10},
        "effect_class": "idempotent",
        "max_attempts": 3,
        "lease_ttl_s": 60,
    }
    evt = Event(
        seq=1,
        event_id="evt_001",
        schema_v=1,
        type=EventType.TASK_CREATED,
        task_id="task-1",
        dedupe_key="k1",
        ts_utc="2026-10-08T12:00:00Z",
        payload=payload,
        prev_hash="0" * 64,
        hash="1" * 64,
    )
    result = _event_json(evt)
    assert result["seq"] == 1
    assert result["event_id"] == "evt_001"
    assert result["type"] == "TASK_CREATED"
    assert result["task_id"] == "task-1"
    assert result["payload"] == payload
    assert result["hash"] == "1" * 64


# -----------------------------------------------------------------------------
# CLI Argument Parsing Tests
# -----------------------------------------------------------------------------

def test_main_arg_parser_validation(tmp_path: Path):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2

    with pytest.raises(SystemExit) as exc:
        main(["--home", str(tmp_path), "--port", "-1"])
    assert exc.value.code == 2

    with pytest.raises(SystemExit) as exc:
        main(["--home", str(tmp_path), "--port", "70000"])
    assert exc.value.code == 2


# -----------------------------------------------------------------------------
# In-Process HTTP Server Lifecycle Tests
# -----------------------------------------------------------------------------

def _http_request(url: str, method: str = "GET", headers: dict | None = None, body: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(url, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req.add_header("Content-Type", "application/json")
        req.add_header("Content-Length", str(len(data)))

    try:
        with urllib.request.urlopen(req, data=data, timeout=5) as resp:
            resp_data = resp.read()
            return resp.status, json.loads(resp_data.decode("utf-8")) if resp_data else {}
    except urllib.error.HTTPError as e:
        err_data = e.read()
        try:
            parsed = json.loads(err_data.decode("utf-8"))
        except Exception:
            parsed = {"raw": err_data.decode("utf-8", errors="replace")}
        return e.code, parsed


def test_service_lifecycle_and_http_endpoints(tmp_path: Path):
    home = tmp_path / "courier_home"
    service = Service(home, port=0)
    assert service.port > 0

    # Running another Service on the same home directory must fail with SystemExit
    with pytest.raises(SystemExit):
        Service(home, port=0)

    # Start server in thread
    t = threading.Thread(target=service.run, daemon=True)
    t.start()

    base_url = f"http://127.0.0.1:{service.port}"
    token = service.token
    auth_headers = {TOKEN_HEADER: token}

    try:
        # 1. Unauthenticated request returns 401
        status, body = _http_request(f"{base_url}/v1/health")
        assert status == 401
        assert body.get("error") == "unauthorized"

        # 2. Invalid token returns 401
        status, body = _http_request(f"{base_url}/v1/health", headers={TOKEN_HEADER: "invalid_token"})
        assert status == 401

        # 3. Valid GET /v1/health
        status, body = _http_request(f"{base_url}/v1/health", headers=auth_headers)
        assert status == 200
        assert "mode" in body
        assert "head_seq" in body

        # 4. Route not found returns 404
        status, body = _http_request(f"{base_url}/v1/nonexistent", headers=auth_headers)
        assert status == 404

        # 5. Method not allowed returns 405
        status, body = _http_request(f"{base_url}/v1/health", method="PUT", headers=auth_headers)
        assert status == 405

        # 6. POST /v1/tasks with valid payload returns 201
        task_payload = {
            "adapter": "synthetic",
            "params": {"duration_ms": 10},
            "effect_class": "idempotent",
            "max_attempts": 3,
            "lease_ttl_s": 60,
        }
        status, body = _http_request(f"{base_url}/v1/tasks", method="POST", headers=auth_headers, body=task_payload)
        assert status == 201
        assert "task_id" in body
        created_task_id = body["task_id"]

        # 7. GET /v1/tasks/<id> returns 200
        status, body = _http_request(f"{base_url}/v1/tasks/{created_task_id}", headers=auth_headers)
        assert status == 200
        assert body["task_id"] == created_task_id

        # 8. POST /v1/shutdown stops the service
        status, body = _http_request(f"{base_url}/v1/shutdown", method="POST", headers=auth_headers)
        assert status == 200
        assert body.get("status") == "STOPPING"

    finally:
        service.shutdown()
        t.join(timeout=3)


def test_service_http_payload_edge_cases(tmp_path: Path):
    home = tmp_path / "courier_home_edge"
    service = Service(home, port=0)
    t = threading.Thread(target=service.run, daemon=True)
    t.start()

    base_url = f"http://127.0.0.1:{service.port}"
    auth_headers = {TOKEN_HEADER: service.token}

    try:
        # Invalid JSON body -> 400
        req = urllib.request.Request(f"{base_url}/v1/tasks", method="POST", data=b"{malformed json")
        for k, v in auth_headers.items():
            req.add_header(k, v)
        req.add_header("Content-Type", "application/json")
        req.add_header("Content-Length", str(len(b"{malformed json")))
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=5)
        assert exc.value.code == 400
        err = json.loads(exc.value.read().decode("utf-8"))
        assert err["error"] == "invalid_json"

        # Oversized body -> 413
        oversized_data = b"x" * (MAX_BODY_BYTES + 10)
        req2 = urllib.request.Request(f"{base_url}/v1/tasks", method="POST", data=oversized_data)
        for k, v in auth_headers.items():
            req2.add_header(k, v)
        req2.add_header("Content-Length", str(len(oversized_data)))
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req2, timeout=5)
        assert exc.value.code == 413
        err = json.loads(exc.value.read().decode("utf-8"))
        assert err["error"] == "too_large"

        # Invalid Last-Event-ID header -> 400
        status, body = _http_request(f"{base_url}/v1/events", headers={TOKEN_HEADER: service.token, "Last-Event-ID": "invalid"})
        assert status == 400
        assert body["error"] == "invalid_request"

    finally:
        service.shutdown()
        t.join(timeout=3)


def test_service_claim_and_execution_lifecycle(tmp_path: Path):
    home = tmp_path / "courier_home_exec"
    service = Service(home, port=0)
    t = threading.Thread(target=service.run, daemon=True)
    t.start()

    base_url = f"http://127.0.0.1:{service.port}"
    auth_headers = {TOKEN_HEADER: service.token}

    try:
        # 1. Claim on empty queue returns 204
        claim_payload = {"worker_id": "worker-1"}
        req = urllib.request.Request(f"{base_url}/v1/claim", method="POST", data=json.dumps(claim_payload).encode("utf-8"))
        for k, v in auth_headers.items():
            req.add_header(k, v)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 204

        # 2. Create task
        task_payload = {
            "adapter": "synthetic",
            "params": {"duration_ms": 5},
            "effect_class": "idempotent",
            "max_attempts": 2,
            "lease_ttl_s": 60,
        }
        status, body = _http_request(f"{base_url}/v1/tasks", method="POST", headers=auth_headers, body=task_payload)
        assert status == 201
        task_id = body["task_id"]

        # 3. Claim created task
        status, lease = _http_request(f"{base_url}/v1/claim", method="POST", headers=auth_headers, body=claim_payload)
        assert status == 200
        assert lease["task_id"] == task_id
        dispatch_id = lease["dispatch_id"]

        # 4. Start task
        start_payload = {"dispatch_id": dispatch_id, "worker_id": "worker-1"}
        status, start_resp = _http_request(f"{base_url}/v1/start", method="POST", headers=auth_headers, body=start_payload)
        assert status == 200

        # 5. Heartbeat
        hb_payload = {"worker_id": "worker-1", "dispatch_ids": [dispatch_id]}
        status, hb_resp = _http_request(f"{base_url}/v1/heartbeat", method="POST", headers=auth_headers, body=hb_payload)
        assert status == 200
        assert "stop" in hb_resp
        assert "cancel" in hb_resp

        # 6. Post Result
        res_payload = {
            "dispatch_id": dispatch_id,
            "result_id": "res-001",
            "artifacts": [],
            "outcome": "success",
        }
        status, res_resp = _http_request(f"{base_url}/v1/result", method="POST", headers=auth_headers, body=res_payload)
        assert status == 200
        assert res_resp["status"] == "ACCEPTED_FOR_VERIFY"

        # 7. Verify task view is accepted or verified
        status, task_view = _http_request(f"{base_url}/v1/tasks/{task_id}", headers=auth_headers)
        assert status == 200
        assert "status" in task_view

    finally:
        service.shutdown()
        t.join(timeout=3)

