"""L4 pins: Enforce 64 KiB maximum parameter and result report size bounds.

Covers QM-B05-RECEIPT-PAYLOAD-MAX-BYTES:
1. validate_request raises SpecError when params > 64 KiB.
2. read_report returns None when report file > 64 KiB.
3. read_report returns valid dict for bounded report files <= 64 KiB.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from courier_worker.adapter_bridge import (
    MAX_PARAMS_BYTES,
    read_report,
    report_path,
    validate_request,
)
from courier_worker.host import SpecError


def test_validate_request_rejects_params_over_64kib():
    large_params = {"big_data": "x" * (MAX_PARAMS_BYTES + 1)}
    spec = {
        "adapter": "synthetic",
        "params": large_params,
        "effect_key": "eff-001",
    }
    with pytest.raises(SpecError, match="exceed the size bound"):
        validate_request(spec)


def test_validate_request_accepts_bounded_params():
    spec = {
        "adapter": "synthetic",
        "params": {"write": "ok.txt", "content": "fine"},
        "effect_key": "eff-001",
    }
    adapter, params, eff = validate_request(spec)
    assert adapter == "synthetic"
    assert eff == "eff-001"


def test_read_report_rejects_report_over_64kib(tmp_path: Path):
    dispatch_id = "disp-oversized"
    rpath = report_path(str(tmp_path), dispatch_id)
    os.makedirs(os.path.dirname(rpath), exist_ok=True)

    oversized_data = {
        "outcome": "success",
        "retryable": False,
        "padding": "x" * (MAX_PARAMS_BYTES + 100),
    }
    with open(rpath, "w", encoding="utf-8") as fh:
        json.dump(oversized_data, fh)

    assert os.path.getsize(rpath) > MAX_PARAMS_BYTES
    assert read_report(str(tmp_path), dispatch_id) is None


def test_read_report_accepts_bounded_report(tmp_path: Path):
    dispatch_id = "disp-bounded"
    rpath = report_path(str(tmp_path), dispatch_id)
    os.makedirs(os.path.dirname(rpath), exist_ok=True)

    normal_data = {
        "outcome": "success",
        "retryable": False,
        "reason": "completed cleanly",
    }
    with open(rpath, "w", encoding="utf-8") as fh:
        json.dump(normal_data, fh)

    assert os.path.getsize(rpath) <= MAX_PARAMS_BYTES
    report = read_report(str(tmp_path), dispatch_id)
    assert report is not None
    assert report["outcome"] == "success"
    assert report["retryable"] is False
