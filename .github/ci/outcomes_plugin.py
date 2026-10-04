"""pytest plugin: record the final outcome of every test node id as JSON.

Loaded with ``-p outcomes_plugin`` (``.github/ci`` must be on PYTHONPATH).
The output path is taken from the COURIER_CI_OUTCOMES environment variable.
An outcome is "failed" if setup, call or teardown failed, "skipped" if the
test was skipped, otherwise "passed". The regression gate
(check_regressions.py) compares these outcomes with known_failures.json.
"""

import json
import os

_OUTCOMES = {}
_RANK = {"passed": 0, "skipped": 1, "failed": 2}


def pytest_runtest_logreport(report):
    if report.failed:
        outcome = "failed"
    elif report.skipped:
        outcome = "skipped"
    else:
        outcome = "passed"
    previous = _OUTCOMES.get(report.nodeid)
    if previous is None or _RANK[outcome] > _RANK[previous]:
        _OUTCOMES[report.nodeid] = outcome


def pytest_collectreport(report):
    if report.failed:
        _OUTCOMES[f"{report.nodeid}::<collection>"] = "failed"


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get("COURIER_CI_OUTCOMES")
    if not path:
        return
    payload = {"exitstatus": int(exitstatus), "outcomes": dict(sorted(_OUTCOMES.items()))}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1)
