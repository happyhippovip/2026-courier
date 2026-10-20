import sys
from unittest.mock import patch
import pytest

from courier_worker.host import default_pressure_probe, _win_memory_status


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific pressure probe test")
def test_win_memory_status_returns_valid_tuple():
    """Windows native memory probe returns valid load percentage and available MB."""
    mem = _win_memory_status()
    assert mem is not None
    load_pct, avail_mb = mem
    assert 0 <= load_pct <= 100
    assert avail_mb > 0


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific pressure probe test")
def test_win_pressure_probe_ram_high_percentage():
    """Windows pressure probe returns ram-pressure when memory load reaches 96%."""
    with patch("courier_worker.host._win_memory_status", return_value=(96, 1024)):
        reason = default_pressure_probe()
        assert reason is not None
        assert "ram-pressure" in reason
        assert "96%" in reason


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific pressure probe test")
def test_win_pressure_probe_ram_low_avail():
    """Windows pressure probe returns ram-pressure when available RAM is below 256MB."""
    with patch("courier_worker.host._win_memory_status", return_value=(80, 128)):
        reason = default_pressure_probe()
        assert reason is not None
        assert "ram-pressure" in reason
        assert "128MB" in reason


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific pressure probe test")
def test_win_pressure_probe_cpu_high():
    """Windows pressure probe returns cpu-pressure when psutil reports CPU >= 95%."""
    with patch("courier_worker.host._win_memory_status", return_value=(50, 4096)), \
         patch("psutil.cpu_percent", return_value=96.5):
        reason = default_pressure_probe()
        assert reason is not None
        assert "cpu-pressure" in reason
        assert "96.5%" in reason
