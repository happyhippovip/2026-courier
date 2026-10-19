"""The agy binary reaches provider_exec only as an absolute path to a file.

These run the real adapter_runner as the worker does, with the binary given
through COURIER_PROVIDER_AGY_BIN (the variable the Windows launcher sets from
config.json). No model is called: the "agy" here is a local fake that prints
the success envelope.
"""
import json
import os
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _fake_agy(tmp_path):
    script = tmp_path / "fake_agy.py"
    script.write_text(textwrap.dedent(f"""\
        #!{sys.executable}
        import json, pathlib, sys
        pathlib.Path({str(tmp_path / 'launched.txt')!r}).write_text(" ".join(sys.argv[1:]))
        print(json.dumps({{"status": "SUCCESS", "response": "noop"}}))
        """), encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def _run_agy_task(tmp_path, agy_bin):
    work = tmp_path / "work"
    work.mkdir()
    request = tmp_path / "request.json"
    report = tmp_path / "report.json"
    request.write_text(json.dumps({
        "adapter": "provider_exec", "workdir": str(work), "report": str(report), "attempt": 1,
        "params": {"provider": "agy", "prompt": "noop"},
    }), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "COURIER_PROVIDER_AGY_BIN"}
    env["PYTHONPATH"] = str(ROOT)
    if agy_bin is not None:
        env["COURIER_PROVIDER_AGY_BIN"] = str(agy_bin)
    done = subprocess.run([sys.executable, "-m", "courier_worker.adapter_runner", str(request)],
                          cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    evidence = (work / "provider_output.txt").read_bytes()
    return json.loads(report.read_text(encoding="utf-8")), evidence


@pytest.mark.parametrize("agy_bin", [None, "agy", "relative/fake_agy.py", "/no/such/agy"])
def test_missing_relative_or_absent_binary_is_never_launched(tmp_path, agy_bin):
    report, evidence = _run_agy_task(tmp_path, agy_bin)
    assert report["outcome"] == "failure"
    assert report["reason"].startswith("BINARY_MISSING")
    assert evidence == b""
    assert not (tmp_path / "launched.txt").exists()


@pytest.mark.skipif(os.name == "nt", reason="the .py fake is started through sys.executable on Windows; covered by the live test")
def test_absolute_fake_binary_is_launched_and_yields_the_checked_envelope(tmp_path, monkeypatch):
    # Cost gate (PR #714) admits agy at 0.0 on the active Antigravity resource.
    report, evidence = _run_agy_task(tmp_path, _fake_agy(tmp_path))
    assert report["outcome"] == "success", report
    assert evidence == b'{"provider":"agy","status":"SUCCESS"}\n'
    launched = (tmp_path / "launched.txt").read_text()
    assert "--dangerously-skip-permissions" not in launched and "--yolo" not in launched
