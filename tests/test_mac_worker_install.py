import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_install_resolves_repo_root_from_any_cwd(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "launchctl").write_text("#!/bin/sh\nexit 0\n")
    (bindir / "launchctl").chmod(0o755)
    env = {"PATH": f"{bindir}:/usr/bin:/bin", "HOME": str(tmp_path)}
    for cwd in (ROOT, tmp_path):
        r = subprocess.run(["bash", str(ROOT / "scripts/mac_worker/install.sh")], cwd=cwd, env=env,
                           capture_output=True, text=True, timeout=30)
        assert r.returncode == 0, r.stderr
        plist = (tmp_path / "Library/LaunchAgents/com.courier.mac_worker.plist").read_text()
        assert f"<string>{ROOT}/scripts/mac_worker/daemon.py</string>" in plist
        assert f"<string>{ROOT}</string>" in plist
        assert "TARGET_DIR" not in plist


def test_keychain_setup_hides_api_key_input():
    text = (ROOT / "scripts/mac_worker/setup_keychain.sh").read_text()
    key_prompt = [line for line in text.splitlines() if "api_key" in line and line.lstrip().startswith("read")]
    import re
    assert key_prompt and all(re.search(r"read\s+-\w*s", line) for line in key_prompt)
