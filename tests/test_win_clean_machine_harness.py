import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import psutil
import pytest

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
sys.path.insert(0, str(GOLDEN_DIR))
from golden_harness import Courier, descendants, pids_alive  # noqa: E402

UNINSTALL_SCRIPT = Path("scripts/windows_worker/uninstall.ps1")
# Live uninstall.ps1 is not executed. It requires Administrator and edits
# machine-wide state: the CourierWindowsWorker scheduled task, Program Files,
# and config/run under every profile in C:\Users. Rule 0 step 12 is checked
# by parsing that script. A live run on a clean machine remains unproven.


@pytest.fixture(autouse=True)
def restore_courier_exe():
    yield
    if os.name == 'nt':
        try:
            subprocess.run(["git", "restore", "scripts/windows_worker/Courier.exe"], check=False)
        except Exception:
            pass


# Destructive forms the contract must see. Remove-Item is not the only one:
# truncation and cmd/IO deletes destroy courier.db and logs just as thoroughly.
# rm and ri are the PowerShell aliases for Remove-Item.
_DESTRUCTIVE_RE = re.compile(
    r"(?i)(?:\b(?:Remove-Item|Clear-Content|Set-Content|Out-File|del|erase|rd|rmdir|rm|ri)\b"
    r"|\[(?:System\.)?IO\.(?:File|Directory)\]::Delete)"
)
_USER_COURIER_DIR_RE = re.compile(
    r"(?i)(?:\$userCourierDir|AppData\\Local\\Courier|LOCALAPPDATA\\Courier)"
)
# An allowlisted child of the user Courier dir. The directory itself, a glob of
# it, or any other child still covers courier.db and logs.
_ALLOWED_CHILD_RE = re.compile(
    r"(?i)Join-Path\s+(?:Join-Path\s+\$_\.FullName\s+\"AppData\\Local\\Courier\"|\$userCourierDir)"
    r"\s+\"(?:config\.json|run)\""
    r"|(?:\$userCourierDir|AppData\\Local\\Courier|LOCALAPPDATA\\Courier)\\(?:config\.json|run)\b"
)
_LOGS_PATH_RE = re.compile(r"(?i)(?:\\|/|['\"])logs(?:\\|/|['\"]|\b)")


def _powershell_assignments(script: str) -> dict[str, str]:
    assigns = {}
    for raw in script.splitlines():
        line = raw.split("#", 1)[0].strip()
        match = re.match(r"\$(\w+)\s*=\s*(.+)$", line)
        if match:
            assigns[match.group(1)] = match.group(2).strip()
    return assigns


def _expand_assignments(text: str, assigns: dict[str, str]) -> str:
    names = sorted(assigns, key=len, reverse=True)
    for _ in range(8):
        updated = text
        for name in names:
            updated = re.sub(
                rf"\${name}\b",
                lambda _m, value=assigns[name]: value,
                updated,
            )
        if updated == text:
            break
        text = updated
    return text


def _powershell_remove_targets(script: str) -> list[str]:
    """Inline simple ``$var = ...`` assignments into Remove-Item targets.

    This is a parse of the script text. It does not execute PowerShell.
    """
    assigns = _powershell_assignments(script)
    targets = []
    for match in re.finditer(r"Remove-Item\b([^\r\n]*)", script):
        args = match.group(1).split("#", 1)[0]
        for token in args.split():
            if token.startswith("-"):
                continue
            token = token.strip("{}")
            if not token or token in {"|"}:
                continue
            expanded = _expand_assignments(token, assigns)
            targets.append(expanded)
    return targets


def _preserved_data_destroyed(expanded: str) -> str | None:
    """Why this destructive line wipes courier.db or logs, or None if it does not."""
    if re.search(r"(?i)courier\.db", expanded):
        return "destroys courier.db"
    if _LOGS_PATH_RE.search(expanded):
        return "destroys logs"
    residual = _ALLOWED_CHILD_RE.sub(" ", expanded)
    if _USER_COURIER_DIR_RE.search(residual):
        return "wipes the user Courier directory (courier.db and logs)"
    return None


def assert_uninstall_preserves_user_data(script: str) -> None:
    """Rule 0 step 12: remove program files, config and run; keep the journal and logs."""
    targets = _powershell_remove_targets(script)
    rendered = "\n".join(targets)
    assert any("ProgramFiles" in target and "CourierWorker" in target for target in targets), rendered
    assert any("config.json" in target for target in targets), rendered
    assert any(re.search(r"""['"]run['"]""", target) for target in targets), rendered
    assigns = _powershell_assignments(script)
    for raw in script.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or not _DESTRUCTIVE_RE.search(line):
            continue
        reason = _preserved_data_destroyed(_expand_assignments(line, assigns))
        assert reason is None, f"{reason}: {line}"
    assert "Database and logs" in script
    assert "preserved" in script.lower()


def test_uninstall_preserves_journal_and_logs_contract():
    """Parse-level Rule 0 uninstall contract. See UNINSTALL_SCRIPT note above."""
    script = UNINSTALL_SCRIPT.read_text(encoding="utf-8")
    assert_uninstall_preserves_user_data(script)


@pytest.mark.parametrize("extra", [
    'Remove-Item -Force (Join-Path $userCourierDir "courier.db")',
    'Remove-Item -Recurse -Force (Join-Path $userCourierDir "logs")',
    'Remove-Item -Recurse -Force "$userCourierDir\\*"',
    "Remove-Item -Recurse -Force $userCourierDir",
    'Remove-Item -Recurse -Force "$env:LOCALAPPDATA\\Courier\\*"',
    'Remove-Item -Recurse -Force (Join-Path $_.FullName "AppData\\Local\\Courier")',
    'Clear-Content -Force (Join-Path $userCourierDir "courier.db")',
    'Clear-Content -Force (Join-Path $userCourierDir "logs\\courier.log")',
    'Set-Content -Path (Join-Path $userCourierDir "courier.db") -Value ""',
    'Out-File -FilePath (Join-Path $userCourierDir "courier.db") -InputObject ""',
    'Out-File -FilePath (Join-Path $userCourierDir "logs\\courier.log") -InputObject ""',
    'cmd /c del /f /q (Join-Path $userCourierDir "courier.db")',
    'cmd /c rd /s /q (Join-Path $userCourierDir "logs")',
    'del /f /q (Join-Path $userCourierDir "courier.db")',
    'rd /s /q (Join-Path $userCourierDir "logs")',
    'rmdir /s /q (Join-Path $userCourierDir "logs")',
    'rm -Recurse -Force $userCourierDir',
    'ri -Force (Join-Path $userCourierDir "courier.db")',
    '[IO.File]::Delete((Join-Path $userCourierDir "courier.db"))',
    '[IO.Directory]::Delete((Join-Path $userCourierDir "logs"), $true)',
    '[System.IO.File]::Delete((Join-Path $userCourierDir "courier.db"))',
    '[System.IO.Directory]::Delete((Join-Path $userCourierDir "logs"), $true)',
])
def test_uninstall_contract_rejects_user_data_destruction(extra):
    """Each forbidden wipe of courier.db or logs must fail the contract."""
    script = UNINSTALL_SCRIPT.read_text(encoding="utf-8")
    with pytest.raises(AssertionError, match=r"courier\.db|logs|user Courier directory"):
        assert_uninstall_preserves_user_data(script + "\n" + extra + "\n")


def test_replay_retries_when_live_journal_advances(tmp_path, monkeypatch):
    """A LEASE_EXPIRED between the live snapshot and the copy is not a hash failure."""

    class Reader:
        def __init__(self, home, logs):
            self.reads = 0

        def projection_hash(self, path=None):
            self.reads += 1
            return "before" if self.reads == 1 else "after"

        def verify_and_rebuild(self, workdir):
            return type("Report", (), {"ok": True})(), "after", "after"

    monkeypatch.setattr(f"{__name__}.Courier", Reader)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    assert _assert_replay_matches_live(tmp_path / "home", tmp_path / "replay") == "after"


def test_replay_still_fails_when_hashes_stay_apart(tmp_path, monkeypatch):
    class Reader:
        def __init__(self, home, logs):
            pass

        def projection_hash(self, path=None):
            return "live"

        def verify_and_rebuild(self, workdir):
            return type("Report", (), {"ok": True})(), "copy", "copy"

    monkeypatch.setattr(f"{__name__}.Courier", Reader)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    with pytest.raises(AssertionError, match=r"copy"):
        _assert_replay_matches_live(tmp_path / "home", tmp_path / "replay")


def _courier_tree(root_pid):
    """The root pid plus Courier-owned descendants. The hub browser is left out."""
    owned = []
    for pid in [root_pid, *descendants(root_pid)]:
        try:
            proc = psutil.Process(pid)
            name = (proc.name() or "").lower()
            try:
                cmd = " ".join(proc.cmdline()).lower()
            except psutil.Error:
                cmd = ""
        except psutil.Error:
            continue
        if pid == root_pid or "courier" in name or "courier" in cmd or name.startswith("python"):
            owned.append(pid)
    return owned


def _offending_pids(home: Path, tracked):
    """Tracked pids still alive, plus any process whose command line uses this home."""
    offenders = set(pids_alive(tracked))
    needle = str(home).lower()
    me = os.getpid()
    for proc in psutil.process_iter(["pid", "cmdline"]):
        pid = proc.info["pid"]
        if pid == me or pid in offenders:
            continue
        try:
            cmd = " ".join(proc.info["cmdline"] or [])
        except (psutil.Error, TypeError):
            continue
        if needle and needle in cmd.lower():
            offenders.add(pid)
    return sorted(offenders)


def _assert_no_orphan_courier_processes(home: Path, tracked, timeout=15):
    """Rule 0 step 7: after Courier closes, none of its processes remain."""
    deadline = time.monotonic() + timeout
    offenders = _offending_pids(home, tracked)
    while offenders and time.monotonic() < deadline:
        time.sleep(0.25)
        offenders = _offending_pids(home, tracked)
    assert offenders == [], f"orphan Courier processes still alive: {offenders}"


def _checkpoint_journal(home: Path):
    """Recover a hard-killed WAL so the read-only golden helpers can open it.

    A read-only open cannot replay a WAL left by taskkill. Checkpointing only
    folds already-committed pages; it does not append a journal event.
    """
    db = home / "courier.db"
    if not db.is_file():
        raise AssertionError(f"missing journal: {db}")
    last_error = None
    for _ in range(5):
        try:
            conn = sqlite3.connect(str(db), timeout=5)
            try:
                conn.execute("PRAGMA wal_checkpoint(FULL)")
            finally:
                conn.close()
            return
        except sqlite3.OperationalError as exc:
            last_error = exc
            time.sleep(0.5)
    raise AssertionError(f"could not checkpoint journal after close: {last_error}")


def _assert_replay_matches_live(home: Path, workdir: Path):
    """Rule 0 step 10: rebuild of the journal matches the live projection.

    The live snapshot and the journal copy are separate reads. While the
    controller is still running, a LEASE_EXPIRED append between them is
    retried. A hash that never settles still fails.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    logs = workdir / "logs"
    logs.mkdir(exist_ok=True)
    reader = Courier(home, logs)
    last_error = None
    live = report = copy_hash = rebuilt_hash = None
    for _ in range(5):
        try:
            live = reader.projection_hash()
            report, copy_hash, rebuilt_hash = reader.verify_and_rebuild(workdir)
        except sqlite3.OperationalError as exc:
            last_error = exc
            time.sleep(0.5)
            continue
        if report.ok and copy_hash == live and rebuilt_hash == live:
            return live
        last_error = (copy_hash, live, rebuilt_hash)
        time.sleep(0.5)
    if not isinstance(last_error, tuple):
        raise AssertionError(f"journal stayed locked during replay: {last_error}")
    assert report.ok, report
    assert copy_hash == live, (copy_hash, live)
    assert rebuilt_hash == live, (rebuilt_hash, live)
    return live


@pytest.mark.skipif(os.name != 'nt', reason="Windows specific clean-machine harness")
def test_win_clean_machine_harness(tmp_path):
    """
    Proves:
    - fresh install
    - first launch
    - single instance
    - Hub/controller startup
    - synthetic work execution
    - shutdown leaves no orphan Courier processes (Rule 0 step 7)
    - restart, and replay/rebuild hash equals the live projection (Rule 0 step 10)
    - user data the uninstall contract preserves is actually on disk (Rule 0 step 12)
    """
    # 1. Fresh install & first launch
    build_script = Path("scripts/windows_worker/launcher/build_launcher.ps1").resolve()
    if build_script.exists():
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(build_script)], check=True)

    launcher_exe = Path("scripts/windows_worker/Courier.exe").resolve()
    assert launcher_exe.exists(), "Courier.exe must be built before tests"

    # Start the launcher
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(tmp_path)
    env["COURIER_TEST_NO_JOB"] = "1"
    env["PYTHONPATH"] = str(Path.cwd())
    # We will use Courier's default ports or force them via config.json
    courier_dir = tmp_path / "Courier"
    courier_dir.mkdir(parents=True)
    
    # Force specific ports via config.json to avoid conflicts
    config_file = courier_dir / "config.json"
    config_file.write_text(json.dumps({
        "COURIER_CONTROLLER_PORT": 8800,
        "COURIER_HUB_PORT": 8801
    }))

    owned_pids = []

    # 0x01000000 is CREATE_BREAKAWAY_FROM_JOB
    try:
        launcher = subprocess.Popen([str(launcher_exe)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x01000000)
    except PermissionError as e:
        if e.winerror == 5:
            # Cannot break away from Job object (e.g. GitHub Actions runner)
            launcher = subprocess.Popen([str(launcher_exe)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            raise

    try:
        # Wait for token
        token_file = courier_dir / "run" / "controller.token"
        start_time = time.monotonic()
        while time.monotonic() - start_time < 30:
            if launcher.poll() is not None:
                out = launcher.stdout.read()
                pytest.fail(f"Launcher exited early with code {launcher.returncode}:\n{out}")
            if token_file.exists():
                token = token_file.read_text().strip()
                if token:
                    break
            time.sleep(0.5)
        else:
            pytest.fail(f"Timeout waiting for controller.token. Launcher output:\n{launcher.stdout.read()}")

        controller_url = "http://127.0.0.1:8800"
        hub_url = "http://127.0.0.1:8801"

        def api(method, path, body=None):
            data = json.dumps(body).encode() if body is not None else None
            req = urllib.request.Request(controller_url + path, data=data, method=method,
                                         headers={"X-Courier-Token": token, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read() or b"{}")

        # Wait for Hub to be up
        start_time = time.monotonic()
        while time.monotonic() - start_time < 30:
            try:
                req = urllib.request.Request(hub_url + "/hub/api/status")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            pytest.fail("Timeout waiting for Hub")

        # 3. Synthetic work execution
        # Normal task
        done_id = api("POST", "/v1/tasks", {
            "adapter": "synthetic", "params": {"sleep_s": 1, "write": "out.txt", "content": "normal"},
            "effect_class": "idempotent", "max_attempts": 3, "lease_ttl_s": 6
        })["task_id"]

        # Non-idempotent task (killed mid-action)
        blocked_id = api("POST", "/v1/tasks", {
            "adapter": "synthetic", "params": {"write": "sent.txt", "content": "message", "hang": True},
            "effect_class": "non_idempotent", "max_attempts": 3, "lease_ttl_s": 6
        })["task_id"]

        # Long-running task
        working_id = api("POST", "/v1/tasks", {
            "adapter": "synthetic", "params": {"sleep_s": 60, "write": "report.txt", "content": "long"},
            "effect_class": "idempotent", "max_attempts": 3, "lease_ttl_s": 6, "timeout_s": 90
        })["task_id"]

        def wait_for(task_id, status_val, timeout=30):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if api("GET", f"/v1/tasks/{task_id}")["status"] == status_val:
                    return
                time.sleep(0.5)
            pytest.fail(f"Timeout waiting for task {task_id} to reach {status_val}")

        wait_for(done_id, "COMPLETE")
        wait_for(blocked_id, "RUNNING")

        # Kill the worker for blocked_id
        # worker.lock is locked with msvcrt.locking on Windows, so we cannot read it directly.
        # Instead, find the claim record for the blocked task.
        claims_dir = courier_dir / "run" / "claims"
        worker_pid = None
        start_wait = time.monotonic()
        while time.monotonic() - start_wait < 10:
            for p in claims_dir.glob("dispatch-*.json"):
                try:
                    record = json.loads(p.read_text())
                    if record.get("task_id") == blocked_id:
                        worker_pid = record["owner_pid"]
                        break
                except Exception:
                    pass
            if worker_pid is not None:
                break
            time.sleep(0.5)
        
        if worker_pid is None:
            print(f"Claims dir {claims_dir} contents: {list(claims_dir.glob('*'))}")
            print(f"Looking for task_id: {blocked_id}")
            for p in claims_dir.glob("dispatch-*.json"):
                try:
                    print(f"File {p.name}: {p.read_text()}")
                except Exception as e:
                    print(f"File {p.name} read error: {e}")
        
        assert worker_pid is not None, "Could not find worker_pid from claims"
        # Record the worker tree before the crash injection. Close must not leave it behind.
        owned_pids.extend(_courier_tree(worker_pid))
        subprocess.run(["taskkill", "/F", "/PID", str(worker_pid)], check=False)
        
        # Wait for blocked task to be blocked (lease expiration takes 6s)
        wait_for(blocked_id, "BLOCKED")

        # Now that the worker is freed, working_id can start
        wait_for(working_id, "RUNNING")

        # Check Hub UI state
        req = urllib.request.Request(hub_url + "/hub/api/home")
        with urllib.request.urlopen(req) as resp:
            home_view = json.loads(resp.read())
            
        assert any(t["id"] == done_id for t in home_view["done"])
        assert any(t["id"] == blocked_id for t in home_view["needs_you"])
        assert any(t["id"] == working_id for t in home_view["working"])

        # Choose "It happened"
        hub_post = urllib.request.Request(hub_url + f"/hub/api/items/{blocked_id}/decision", 
                                          data=json.dumps({"decision": "effect_confirmed", "attempt": 1}).encode(),
                                          method="POST",
                                          headers={"X-Courier-Hub": "1", "Content-Type": "application/json"})
        with urllib.request.urlopen(hub_post) as resp:
            assert resp.status == 200

        # Wait for blocked task to complete
        wait_for(blocked_id, "COMPLETE")

    finally:
        owned_pids.extend(_courier_tree(launcher.pid))
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(launcher.pid)], check=False)
        launcher.wait(10)

    # Rule 0 step 7 — close leaves no Courier processes.
    _assert_no_orphan_courier_processes(courier_dir, owned_pids)
    # Frozen journal after close replays to the same projection.
    _checkpoint_journal(courier_dir)
    _assert_replay_matches_live(courier_dir, tmp_path / "replay-after-close")

    # 4. Restart and Replay
    # 0x01000000 is CREATE_BREAKAWAY_FROM_JOB
    try:
        launcher2 = subprocess.Popen([str(launcher_exe)], env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x01000000)
    except PermissionError as e:
        if getattr(e, "winerror", None) == 5:
            launcher2 = subprocess.Popen([str(launcher_exe)], env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            raise
    restart_pids = []
    try:
        start_time = time.monotonic()
        while time.monotonic() - start_time < 30:
            try:
                req = urllib.request.Request(hub_url + "/hub/api/status")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            pytest.fail("Timeout waiting for Hub after restart")

        req = urllib.request.Request(hub_url + "/hub/api/home")
        with urllib.request.urlopen(req) as resp:
            home_view = json.loads(resp.read())
            
        # done_id should still be done
        assert any(t["id"] == done_id for t in home_view["done"])
        # blocked_id was confirmed, so it's done now
        assert any(t["id"] == blocked_id for t in home_view["done"])

        # Check that no worker lock exists from old process, wait for worker to boot up
        time.sleep(2)
        # Rule 0 step 10 — after restart, replay/rebuild equals the live projection.
        # An in-flight lease may journal LEASE_EXPIRED during restart grace, so this
        # compares rebuild to the live projection at this moment, not to the pre-close hash.
        _assert_replay_matches_live(courier_dir, tmp_path / "replay-after-restart")

    finally:
        restart_pids.extend(_courier_tree(launcher2.pid))
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(launcher2.pid)], check=False)
        launcher2.wait(10)

    _assert_no_orphan_courier_processes(courier_dir, restart_pids)

    # Rule 0 step 12 — the run produced the user data uninstall must keep.
    # The script itself is not executed here (see the module note).
    assert (courier_dir / "courier.db").is_file()
    assert (courier_dir / "logs").is_dir()
    assert (courier_dir / "config.json").is_file()
    assert (courier_dir / "run").is_dir()
    assert_uninstall_preserves_user_data(UNINSTALL_SCRIPT.read_text(encoding="utf-8"))
