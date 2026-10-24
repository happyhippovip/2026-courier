"""F-C1b: a local_shell request without a known cost does not start, even if it reached the runner."""
import json
import sys

import pytest

from courier_worker import adapter_runner


def _request(tmp_path, **params):
    marker = tmp_path / "started"
    argv = [sys.executable, "-c", f"open({str(marker)!r}, 'w').write('x'); open('out.txt', 'w').write('x')"]
    req = tmp_path / "req.json"
    req.write_text(json.dumps({"adapter": "local_shell", "workdir": str(tmp_path / "wd"),
                               "report": str(tmp_path / "report.json"), "attempt": 1,
                               "params": dict({"command": argv, "write": "out.txt"}, **params)}))
    return req, marker


@pytest.mark.parametrize("params", [{}, {"estimated_cost_eur": None}, {"estimated_cost_eur": float("nan")},
                                    {"estimated_cost_eur": 0.5}, {"estimated_cost_eur": 0.0, "unknown_cost": True},
                                    {"estimated_cost_eur": True}])
def test_unknown_or_paid_cost_never_starts_the_command(tmp_path, params):
    req, marker = _request(tmp_path, **params)
    assert adapter_runner.main([str(req)]) == 0
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["outcome"] == "failure" and report["reason"].startswith("cost_blocked")
    assert report["retryable"] is False and not marker.exists()


def test_an_explicit_zero_runs(tmp_path):
    req, marker = _request(tmp_path, estimated_cost_eur=0.0)
    assert adapter_runner.main([str(req)]) == 0
    assert json.loads((tmp_path / "report.json").read_text())["outcome"] == "success" and marker.exists()
