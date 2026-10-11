"""P9 pins for courier_worker.service: main() refusal messages (offline only).

Tests only; no behavior change. No network calls and no filesystem writes:
every case below exits inside argparse, before any WorkerLoop, home lock,
token read, or controller contact exists.

This complements — and does not duplicate — the exit-code pins in
tests/test_worker_service_argv_pins.py (open PR #418) and the offline pins
in tests/test_p9_service_offline.py (open PR #471), which assert exit
codes but never the stderr text operators actually read.
"""

from __future__ import annotations

import pytest

import courier_worker.service as service


def _refusal(argv, capsys):
    """Run main() with bad argv; return (stdout, stderr) after exit code 2."""
    with pytest.raises(SystemExit) as excinfo:
        service.main(argv)
    assert excinfo.value.code == 2
    return capsys.readouterr()


@pytest.mark.parametrize("bad", ["0", "2", "3"])
def test_max_tasks_refusal_names_single_flight(capsys, bad):
    out, err = _refusal(["--controller", "http://127.0.0.1:9", "--max-tasks", bad], capsys)
    assert "supports exactly 1" in err
    assert "supports exactly 1" not in out


def test_max_tasks_non_integer_reports_type_error(capsys):
    out, err = _refusal(
        ["--controller", "http://127.0.0.1:9", "--max-tasks", "many"], capsys)
    assert "invalid int value" in err
    assert "invalid int value" not in out


@pytest.mark.parametrize("bad", ["0.1", "30.1"])
def test_heartbeat_out_of_range_reports_bounds(capsys, bad):
    out, err = _refusal(
        ["--controller", "http://127.0.0.1:9", "--heartbeat", bad], capsys)
    assert "must be within [0.2, 30.0]" in err
    assert "must be within [0.2, 30.0]" not in out


def test_missing_controller_reports_required_flag(capsys):
    out, err = _refusal([], capsys)
    assert "required" in err
    assert "--controller" in err
    assert "required" not in out


def test_refusal_usage_names_worker_prog(capsys):
    _, err = _refusal(["--controller", "http://127.0.0.1:9", "--max-tasks", "2"], capsys)
    assert "courier_worker.host" in err
