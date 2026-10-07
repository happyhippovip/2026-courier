"""Host pressure admission fails closed when the load probe cannot run."""

from unittest.mock import patch

from scripts.resource_governor import HostPressureController


def test_load_probe_oserror_is_unknown_and_refuses_heavy():
    """os.getloadavg OSError is UNKNOWN, and HEAVY work is not admitted.

    Current admit_job treats UNKNOWN like a healthy state and returns True
    (measure_pressure already returns UNKNOWN from the broad except).
    """
    controller = HostPressureController()
    with patch("os.getloadavg", side_effect=OSError("probe failed"), create=True):
        assert controller.measure_pressure() == "UNKNOWN"
        assert controller.admit_job("HEAVY") is False
