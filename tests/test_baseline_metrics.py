"""Dedicated tests for scripts/soak/baseline_metrics.py (P9: baseline_metrics).

Covers the pure slope helper, directory sizing, platform n/a branches, and
the never-raises contract of collect_sample (psutil present and absent).
"""

import os

import pytest

from scripts.soak import baseline_metrics as bm


def test_slope_needs_two_points():
    assert bm.slope([], []) == 0.0
    assert bm.slope([1.0], [2.0]) == 0.0


def test_slope_flat_and_zero_denominator():
    assert bm.slope([1.0, 1.0, 1.0], [5.0, 5.0, 5.0]) == 0.0
    assert bm.slope([0.0, 1.0, 2.0], [3.0, 3.0, 3.0]) == 0.0


def test_slope_linear():
    assert bm.slope([0.0, 1.0, 2.0], [0.0, 2.0, 4.0]) == pytest.approx(2.0)


def test_dir_bytes_counts_files(tmp_path):
    (tmp_path / "a.log").write_bytes(b"x" * 10)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.log").write_bytes(b"y" * 5)
    out = bm._dir_bytes([str(tmp_path)])
    assert out == {"bytes": 15, "files": 2}


def test_dir_bytes_skips_missing_and_empty():
    assert bm._dir_bytes(["/does/not/exist", "", None]) == {"bytes": 0,
                                                            "files": 0}
    assert bm._dir_bytes([]) == {"bytes": 0, "files": 0}


def test_windows_native_off_windows_is_na():
    if os.name == "nt":
        pytest.skip("windows-only branch")
    out = bm._windows_native(None)
    assert out["status"] == "n/a"
    assert out["reason"] == "not-windows"


def test_mac_native_has_status_key():
    out = bm._mac_native()
    assert out["status"] in ("observed", "n/a")


def test_collect_sample_never_raises_and_has_core_keys(tmp_path):
    sample = bm.collect_sample(log_dirs=(str(tmp_path),))
    assert isinstance(sample["timestamp"], float)
    assert isinstance(sample["platform"], str)
    assert sample["log_temp"] == {"bytes": 0, "files": 0}
    assert sample["mac_native"]["status"] in ("observed", "n/a")
    assert sample["windows_native"]["status"] in ("observed", "n/a")


def test_collect_sample_without_psutil_reports_na(monkeypatch, tmp_path):
    monkeypatch.setattr(bm, "_psutil", lambda: None)
    sample = bm.collect_sample(log_dirs=(str(tmp_path),))
    assert sample["psutil"].startswith("n/a:")
    assert "owned_process_count" not in sample
