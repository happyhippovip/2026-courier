import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ["deploy/install_mac_runtime.sh", "scripts/setup_local_autonomy.sh", "scripts/revenue_v1_goal.sh"]
# Known leaked values, stored split so this file is not itself a copy.
LEAKED = ["prod-secret-" + "12345", "ver-secret-" + "67890"]
PENDING_ELSEWHERE = set()
DUMMY = "dummy-test-key-not-real"


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines() if (ROOT / f).is_file()]


def test_no_leaked_credential_in_tracked_source():
    hits = []
    for f in tracked_files():
        if f in PENDING_ELSEWHERE:
            continue
        text = (ROOT / f).read_bytes().decode("utf-8", "ignore")
        hits += [f for s in LEAKED if s in text]
    assert hits == [], f"leaked credential still present in: {sorted(set(hits))}"


@pytest.mark.parametrize("script", SCRIPTS)
def test_scripts_read_key_from_environment(script):
    text = (ROOT / script).read_text()
    assert "${COURIER_API_KEY}" in text
    assert "set -x" not in text


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("key", [None, "", "   "])
def test_missing_key_fails_closed_before_side_effects(script, key, tmp_path):
    # Fake HOME and PATH-shadowed tools prove nothing runs past the guard.
    bindir = tmp_path / "bin"
    bindir.mkdir()
    marker = tmp_path / "called"
    for tool in ("curl", "launchctl", "rm", "cp", "mkdir", "cat"):
        p = bindir / tool
        p.write_text(f"#!/bin/sh\necho {tool} >> {marker}\n")
        p.chmod(0o755)
    env = {"PATH": f"{bindir}:/usr/bin:/bin", "HOME": str(tmp_path), "COURIER_VERIFIER_API_KEY": DUMMY}
    if key is not None:
        env["COURIER_API_KEY"] = key
    r = subprocess.run(["bash", str(ROOT / script)], env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode != 0
    assert "COURIER_API_KEY" in r.stderr
    assert not marker.exists()


def test_revenue_script_uses_key_and_never_echoes_it(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    argsfile = tmp_path / "curl_args"
    curl = bindir / "curl"
    curl.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > {argsfile}\n')
    curl.chmod(0o755)
    env = {"PATH": f"{bindir}:/usr/bin:/bin", "COURIER_API_KEY": DUMMY, "COURIER_SERVER_URL": "http://example.invalid:9/"}
    r = subprocess.run(["bash", str(ROOT / "scripts/revenue_v1_goal.sh")], env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    args = argsfile.read_text()
    assert f"Authorization: Bearer {DUMMY}" in args
    assert "http://example.invalid:9/goals" in args
    assert DUMMY not in r.stdout + r.stderr


def test_revenue_script_prefers_canonical_courier_server(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    argsfile = tmp_path / "curl_args"
    (bindir / "curl").write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > {argsfile}\n')
    (bindir / "curl").chmod(0o755)
    env = {"PATH": f"{bindir}:/usr/bin:/bin", "COURIER_API_KEY": DUMMY,
           "COURIER_SERVER": "http://canonical.invalid:1", "COURIER_SERVER_URL": "http://legacy.invalid:2"}
    r = subprocess.run(["bash", str(ROOT / "scripts/revenue_v1_goal.sh")], env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    assert "http://canonical.invalid:1/goals" in argsfile.read_text()


def test_linux_install_installs_requests_and_never_overwrites_env():
    text = (ROOT / "deploy/install.sh").read_text()
    assert re.search(r"pip install [^\n]*\brequests\b", text)
    assert "if [ ! -f deploy/.env ]" in text
    assert "systemctl restart courier" not in [l.strip() for l in text.splitlines()]
    assert "systemctl enable courier" in [l.strip() for l in text.splitlines()]


def test_local_env_files_are_git_ignored():
    for path in ("deploy/.env", ".env"):
        r = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT)
        assert r.returncode == 0, path
