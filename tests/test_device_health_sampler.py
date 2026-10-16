"""Tests for Device Health Sampler (FRZ-03)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest import mock

import pytest

from scripts.device_health_sampler import (
    check_endpoint_responsiveness,
    evaluate_health_status,
    get_health_summary,
    record_sample_to_db,
    record_sample_to_jsonl,
    sample_resources,
)


def test_sample_resources_keys():
    """Verify sample_resources produces expected dictionary schema."""
    sample = sample_resources()
    assert isinstance(sample, dict)
    assert "timestamp" in sample
    assert "platform" in sample
    assert "cpu_percent" in sample
    assert "memory_percent" in sample
    assert "memory_used_mb" in sample
    assert "disk_percent" in sample
    assert "disk_free_gb" in sample
    assert "process_count" in sample
    assert "handle_count" in sample


def test_evaluate_health_status_ok():
    """Verify normal resources produce OK verdict."""
    sample = {
        "memory_percent": 45.0,
        "cpu_percent": 15.0,
        "disk_percent": 50.0,
        "disk_free_gb": 100.0,
    }
    verdict = evaluate_health_status(sample)
    assert verdict["status"] == "OK"
    assert len(verdict["warnings"]) == 0


def test_evaluate_health_status_warning_memory():
    """Verify memory >= 80% produces WARNING verdict (incident scenario)."""
    sample = {
        "memory_percent": 81.5,
        "cpu_percent": 12.0,
        "disk_percent": 50.0,
        "disk_free_gb": 100.0,
    }
    verdict = evaluate_health_status(sample)
    assert verdict["status"] == "WARNING"
    assert any("memory pressure" in w.lower() for w in verdict["warnings"])


def test_evaluate_health_status_critical():
    """Verify critical thresholds (mem >= 90% or disk free < 1GB)."""
    sample = {
        "memory_percent": 92.0,
        "cpu_percent": 96.0,
        "disk_percent": 99.0,
        "disk_free_gb": 0.5,
    }
    verdict = evaluate_health_status(sample)
    assert verdict["status"] == "CRITICAL"
    assert len(verdict["warnings"]) >= 2


def test_record_sample_to_db_and_summary(tmp_path: Path):
    """Verify database recording and summary retrieval with bounded retention."""
    db_file = tmp_path / "courier.db"
    
    # Record multiple samples
    for i in range(5):
        sample = {
            "timestamp": f"2026-10-09T10:0{i}:00Z",
            "cpu_percent": 10.0 + i,
            "memory_percent": 50.0 + i,
            "memory_used_mb": 4000.0,
            "disk_percent": 40.0,
            "disk_free_gb": 50.0,
            "process_count": 100,
            "handle_count": 500,
        }
        record_sample_to_db(sample, db_file, max_records=3)

    summary = get_health_summary(db_file, limit=10)
    # Because max_records was 3, only 3 rows should remain
    assert len(summary) == 3
    # Most recent sample first
    assert summary[0]["cpu_percent"] == 14.0


def test_record_sample_to_jsonl(tmp_path: Path):
    """Verify JSONL file recording and line pruning."""
    jsonl_file = tmp_path / "samples.jsonl"
    for i in range(10):
        sample = {"index": i, "val": "data"}
        record_sample_to_jsonl(sample, jsonl_file, max_lines=4)

    assert jsonl_file.is_file()
    lines = jsonl_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4
    last = json.loads(lines[-1])
    assert last["index"] == 9


def test_check_endpoint_responsiveness_mock():
    """Verify endpoint responsiveness probing with mock."""
    with mock.patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = mock.MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = check_endpoint_responsiveness("http://127.0.0.1:8080/health")
        assert res["available"] is True
        assert res["status_code"] == 200
        assert res["error"] is None
        assert res["latency_ms"] >= 0.0
