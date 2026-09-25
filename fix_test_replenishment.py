from pathlib import Path
p = Path("tests/test_auto_replenishment.py")
content = p.read_text()

import re

# We need to replace the setup fixture
target = """@pytest.fixture(scope="module")
def setup_runtime():
    if os.path.exists("/tmp/mock_replenish.txt"):
        os.remove("/tmp/mock_replenish.txt")

    state_file = Path.home() / ".courier_runtime" / "server" / "state" / "central_state.json"
    if state_file.exists():
        state_file.unlink()

    server_proc = subprocess.Popen([python_exe, "-m", "server.app"], env=env, cwd=str(Path.home() / ".courier_runtime"))
    verifier_proc = subprocess.Popen([python_exe, str(REPO_ROOT / "scripts/courier_verifier.py")], env=env, cwd=str(Path.home() / ".courier_runtime"))
    time.sleep(3)
    yield
    print("Stopping server...")
    server_proc.terminate()
    verifier_proc.terminate()
    server_proc.wait()
    verifier_proc.wait()"""

replacement = """@pytest.fixture(scope="module")
def setup_runtime():
    import tempfile, shutil
    if os.path.exists("/tmp/mock_replenish.txt"):
        os.remove("/tmp/mock_replenish.txt")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        state_dir = tmp_path / "server" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        env["COURIER_STATE_FILE"] = str(state_dir / "central_state.json")
        env["PYTHONPATH"] = str(REPO_ROOT)

        server_proc = subprocess.Popen([python_exe, "-m", "server.app"], env=env, cwd=tmpdir)
        verifier_proc = subprocess.Popen([python_exe, str(REPO_ROOT / "scripts/courier_verifier.py")], env=env, cwd=tmpdir)
        time.sleep(3)
        yield
        print("Stopping server...")
        server_proc.terminate()
        verifier_proc.terminate()
        server_proc.wait()
        verifier_proc.wait()"""

if target in content:
    content = content.replace(target, replacement)
    p.write_text(content)
    print("SUCCESS")
else:
    print("FAILED TO FIND TARGET")
