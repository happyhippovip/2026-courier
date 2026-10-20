from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from courier_core.outbox_drain import drain_outbox, OutboxDrainReport


def test_drain_empty_outbox(tmp_path: Path):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    report = drain_outbox(tmp_path, deliver_fn=lambda p: True)

    assert isinstance(report, OutboxDrainReport)
    assert report.success is True
    assert report.drained_count == 0
    assert report.remaining_count == 0
    assert report.corrupt_count == 0


def test_drain_outbox_happy_path(tmp_path: Path):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    f1 = outbox / "d-1.json"
    f1.write_text(json.dumps({"dispatch_id": "d-1", "outcome": "completed"}), encoding="utf-8")
    f2 = outbox / "d-2.json"
    f2.write_text(json.dumps({"dispatch_id": "d-2", "outcome": "completed"}), encoding="utf-8")

    delivered = []

    def mock_deliver(payload):
        delivered.append(payload["dispatch_id"])
        return True

    report = drain_outbox(tmp_path, deliver_fn=mock_deliver)
    assert report.success is True
    assert report.drained_count == 2
    assert report.remaining_count == 0
    assert set(delivered) == {"d-1", "d-2"}
    assert not f1.exists()
    assert not f2.exists()


def test_drain_outbox_partial_failure(tmp_path: Path):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    f_ok = outbox / "ok.json"
    f_ok.write_text(json.dumps({"dispatch_id": "ok"}), encoding="utf-8")
    f_fail = outbox / "fail.json"
    f_fail.write_text(json.dumps({"dispatch_id": "fail"}), encoding="utf-8")

    def mock_deliver(payload):
        return payload["dispatch_id"] == "ok"

    report = drain_outbox(tmp_path, deliver_fn=mock_deliver)
    assert report.drained_count == 1
    assert report.remaining_count == 1
    assert not f_ok.exists()
    assert f_fail.exists()


def test_drain_outbox_handles_corrupt_file(tmp_path: Path):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    f_bad = outbox / "corrupt.json"
    f_bad.write_text("{broken json", encoding="utf-8")

    report = drain_outbox(tmp_path, deliver_fn=lambda p: True)
    assert report.corrupt_count == 1
    assert not f_bad.exists()
    corrupt_dir = outbox / "corrupt"
    assert corrupt_dir.exists()
    assert (corrupt_dir / "corrupt.json").exists()


def test_drain_outbox_respects_max_items_limit(tmp_path: Path):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    for i in range(5):
        (outbox / f"item-{i}.json").write_text(json.dumps({"dispatch_id": f"item-{i}"}), encoding="utf-8")

    report = drain_outbox(tmp_path, deliver_fn=lambda p: True, max_items=2)
    assert report.drained_count == 2
    assert report.remaining_count == 3


def test_cli_invocation_dry_run_and_execution(tmp_path: Path):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "d-cli.json").write_text(json.dumps({"dispatch_id": "d-cli"}), encoding="utf-8")

    # Dry-run
    res_dry = subprocess.run(
        [sys.executable, "-m", "courier_core.outbox_drain", str(tmp_path), "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert res_dry.returncode == 0
    data_dry = json.loads(res_dry.stdout)
    assert data_dry["remaining_count"] == 1
    assert (outbox / "d-cli.json").exists()

    # Non-dry-run without deliver_fn / --deliver-dir must fail closed (returncode 1)
    res_no_handler = subprocess.run(
        [sys.executable, "-m", "courier_core.outbox_drain", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert res_no_handler.returncode == 1
    data_no_handler = json.loads(res_no_handler.stdout)
    assert data_no_handler["success"] is False
    assert (outbox / "d-cli.json").exists()

    # Non-dry-run with --deliver-dir delivers and drains
    deliver_dir = tmp_path / "delivered"
    res_exec = subprocess.run(
        [sys.executable, "-m", "courier_core.outbox_drain", str(tmp_path), "--deliver-dir", str(deliver_dir)],
        capture_output=True,
        text=True,
    )
    assert res_exec.returncode == 0
    data_exec = json.loads(res_exec.stdout)
    assert data_exec["success"] is True
    assert data_exec["drained_count"] == 1
    assert not (outbox / "d-cli.json").exists()
    assert (deliver_dir / "d-cli.json").exists()
