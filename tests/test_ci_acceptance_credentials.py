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
