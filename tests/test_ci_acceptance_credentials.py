import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "courier_motor.yml"
ACCEPTANCE = ROOT / "scripts" / "acceptance" / "run_final_acceptance.py"
KEY_VARS = ("COURIER_API_KEY", "COURIER_VERIFIER_API_KEY")


def motor_env():
    wf = yaml.safe_load(WORKFLOW.read_text())
    step = next(s for s in wf["jobs"]["motor"]["steps"] if s.get("name") == "Run Courier Motor")
    return step


def test_workflow_uses_secret_references_not_literals():
    env = motor_env()["env"]
    for var in KEY_VARS:
        assert env[var] == "${{ secrets.%s }}" % var


def test_workflow_ephemeral_fallback_is_masked_and_generated():
    run = motor_env()["run"]
    assert "secrets.token_hex" in run
    assert "::add-mask::" in run


def test_acceptance_has_no_literal_keys():
    src = ACCEPTANCE.read_text()
    assert not re.search(r'^(VERIFIER_)?API_KEY\s*=\s*["\']', src, re.M)
    for var in KEY_VARS:
        assert f'os.environ.get("{var}"' in src


def test_acceptance_missing_keys_fail_closed_without_starting_server(tmp_path):
    dummy = "dummy-verifier-key-not-real"
    env = {"PATH": "/usr/bin:/bin", "COURIER_VERIFIER_API_KEY": dummy}
    r = subprocess.run([sys.executable, str(ACCEPTANCE)], cwd=tmp_path, env=env,
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 2
    assert "COURIER_API_KEY" in r.stderr
    assert "Server started" not in r.stdout
    assert dummy not in r.stdout + r.stderr


def _motor_key_block():
    run = motor_env()["run"]
    start = run.index("for var in COURIER_API_KEY")
    end = run.index("done", start) + len("done")
    return run[start:end]


def test_workflow_fallback_keys_are_distinct_and_only_emitted_as_masks():
    script = _motor_key_block() + '\necho "API=$COURIER_API_KEY" > "$OUT"; echo "VER=$COURIER_VERIFIER_API_KEY" >> "$OUT"'
    import os
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "keys")
        r = subprocess.run(["bash", "-c", script], env={"PATH": "/usr/bin:/bin", "OUT": out},
                           capture_output=True, text=True, timeout=30)
        assert r.returncode == 0, r.stderr
        keys = dict(line.split("=", 1) for line in open(out).read().split())
    api, ver = keys["API"], keys["VER"]
    assert len(api) >= 32 and len(ver) >= 32 and api != ver  # server requires distinct keys
    for line in r.stdout.splitlines():
        if api in line or ver in line:
            assert line.startswith("::add-mask::")


def test_workflow_uses_provided_secrets_without_regenerating():
    r = subprocess.run(["bash", "-c", _motor_key_block() + '\necho "$COURIER_API_KEY|$COURIER_VERIFIER_API_KEY"'],
                       env={"PATH": "/usr/bin:/bin", "COURIER_API_KEY": "dummy-a-not-real",
                            "COURIER_VERIFIER_API_KEY": "dummy-v-not-real"},
                       capture_output=True, text=True, timeout=30)
    assert r.stdout.strip().splitlines()[-1] == "dummy-a-not-real|dummy-v-not-real"
    assert "ephemeral" not in r.stdout


def test_no_workflow_hardcodes_courier_keys_or_echoes_them():
    for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
        text = wf.read_text()
        assert not re.search(r"COURIER_(VERIFIER_)?API_KEY:\s*[\"']?[A-Za-z0-9_-]{6,}", text), wf.name
        assert not re.search(r"echo[^\n]*\$\{?COURIER_(VERIFIER_)?API_KEY", text), wf.name
        assert "set -x" not in text, wf.name
