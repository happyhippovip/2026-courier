"""L3 registration of the trunk provider_exec adapter.

Proves the bridge dict contains provider_exec and the runner allowlist
accepts a request for it. The binary is absent, so nothing is launched.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from courier_worker import adapter_bridge as bridge
from courier_worker import adapter_runner


def test_adapters_contains_provider_exec():
    assert "provider_exec" in bridge.ADAPTERS
    assert bridge.ADAPTERS["provider_exec"] is bridge._validate_provider_exec


def test_runner_allowlist_accepts_provider_exec(tmp_path):
    assert "provider_exec" in adapter_runner.ALLOWED
    workdir = tmp_path / "work"
    report = tmp_path / "report.json"
    request = tmp_path / "request.json"
    request.write_text(json.dumps({
        "adapter": "provider_exec",
        "params": {"provider": "muse", "prompt": "unit"},
        "attempt": 1,
        "workdir": str(workdir),
        "report": str(report),
    }), encoding="utf-8")
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("COURIER_PROVIDER_")}
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run(
        [sys.executable, bridge.RUNNER_SCRIPT, str(request)],
        cwd=env["PYTHONPATH"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "not allowlisted" not in proc.stderr
    body = json.loads(report.read_text(encoding="utf-8"))
    assert body["outcome"] == "failure"
    assert body["retryable"] is False
    assert "BINARY_MISSING" in body["reason"]
    assert (workdir / "provider_output.txt").is_file()
