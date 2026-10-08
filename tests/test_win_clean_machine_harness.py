import json
import os
import re
import shutil
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
# The parse-level Rule 0 contract below does not execute uninstall.ps1.
# prove_live_uninstall() does, and only when live_uninstall_permitted() is
# true: GITHUB_ACTIONS=true and COURIER_HARNESS_LIVE_UNINSTALL=1. CI=true
# alone is not permission. A dev machine must never hit Program Files.
PACKAGE_DIR_ENV = "COURIER_HARNESS_PACKAGE_DIR"
LIVE_UNINSTALL_ENV = "COURIER_HARNESS_LIVE_UNINSTALL"
EVIDENCE_ENV = "COURIER_HARNESS_EVIDENCE_DIR"
_JOURNAL_MARKER = b"courier-clean-machine-journal-marker\n"
_LOG_MARKER = "courier-clean-machine-log-marker\n"
_CONFIG_MARKER = "courier-clean-machine"
_DROPPED_ENV = (
    "PYTHONPATH",
    "PYTHONHOME",
    "PYTHONSTARTUP",
    "PYTHONUSERBASE",
    "VIRTUAL_ENV",
    "COURIER_HOME",
)
_SECRET_ENV = re.compile(r"(?i)(TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|API_KEY|PRIVATE_KEY)")
_SECRET_TEXT = re.compile(r"(?i)(token|secret|password|api[_-]?key)(\s*[=:]\s*)(\S+)")
_LONG_HEX = re.compile(r"\b[0-9a-fA-F]{32,}\b")


def packaged_root() -> Path | None:
    """Package directory from COURIER_HARNESS_PACKAGE_DIR, or None for repo mode."""
    raw = os.environ.get(PACKAGE_DIR_ENV, "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_dir():
        raise AssertionError(f"{PACKAGE_DIR_ENV} is not a directory: {raw}")
    return path.resolve()


def package_child_env(local_app_data: Path, base: dict | None = None) -> dict:
    """Environment for the packaged launcher.

    System Python is removed from PATH. PYTHONPATH and PYTHONHOME are unset.
    LOCALAPPDATA is an isolated root; the launcher appends \\Courier.
    """
    env = dict(os.environ if base is None else base)
    dropped = {name.casefold() for name in _DROPPED_ENV}
    dropped.add("path")
    for key in list(env):
        if key.casefold() in dropped or _SECRET_ENV.search(key):
            env.pop(key, None)
    system_root = str(env.get("SystemRoot") or env.get("SYSTEMROOT") or r"C:\Windows").rstrip("\\/")
    env["PATH"] = ";".join([
        system_root + r"\system32",
        system_root,
        system_root + r"\System32\Wbem",
    ])
    env["LOCALAPPDATA"] = str(local_app_data)
    env["COURIER_TEST_NO_JOB"] = "1"
    return env


def live_uninstall_permitted() -> bool:
    """True only for the GitHub-hosted job that opted into the live proof."""
    return os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get(LIVE_UNINSTALL_ENV) == "1"


def redact_evidence(text: str) -> str:
    text = _SECRET_TEXT.sub(r"\1\2[redacted]", text)
    return _LONG_HEX.sub("[redacted]", text)


def evidence_root(repo: Path | None = None) -> Path | None:
    raw = os.environ.get(EVIDENCE_ENV, "").strip()
    if not raw:
        return None
    path = Path(raw).resolve()
    root = (repo or Path.cwd()).resolve()
    if path == root or root in path.parents:
        raise AssertionError(f"evidence directory is inside the working tree: {path}")
    return path


def write_evidence(name: str, text: str, repo: Path | None = None) -> None:
    if name != Path(name).name or name in {"", ".", ".."}:
        raise AssertionError(f"evidence name must be a single file name: {name}")
    root = evidence_root(repo)
    if root is None:
        return
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(redact_evidence(text), encoding="utf-8")


def _powershell(command: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
    )


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
_DESTRUCTIVE_RE = re.compile(
    r"(?i)(?:\b(?:Remove-Item|Clear-Content|Set-Content|Out-File|del|erase|rd|rmdir)\b"
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


def _task_query() -> subprocess.CompletedProcess:
    return _powershell(
        "if (Get-ScheduledTask -TaskName 'CourierWindowsWorker' -ErrorAction SilentlyContinue) "
        "{ exit 0 } else { exit 2 }"
    )


def _cleanup_live_uninstall(home: Path, install_dir: Path) -> None:
    """Remove only the markers this proof created. Leave any other user data."""
    db = home / "courier.db"
    try:
        if db.is_file() and db.read_bytes().startswith(_JOURNAL_MARKER):
            db.unlink()
    except OSError:
        pass
    log = home / "logs" / "courier.log"
    logs = home / "logs"
    try:
        if log.is_file() and _LOG_MARKER in log.read_text(encoding="utf-8", errors="replace"):
            log.unlink()
        if logs.is_dir() and not any(logs.iterdir()):
            logs.rmdir()
    except OSError:
        pass
    config = home / "config.json"
    try:
        if config.is_file() and _CONFIG_MARKER in config.read_text(encoding="utf-8", errors="replace"):
            config.unlink()
    except OSError:
        pass
    run = home / "run"
    try:
        marker = run / "marker.txt"
        if marker.is_file() and marker.read_text(encoding="utf-8").strip() == "remove-me":
            marker.unlink()
        if run.is_dir() and not any(run.iterdir()):
            run.rmdir()
    except OSError:
        pass
    try:
        if home.is_dir() and not any(home.iterdir()):
            home.rmdir()
    except OSError:
        pass
    if install_dir.exists():
        shutil.rmtree(install_dir, ignore_errors=True)
    _powershell(
        "Unregister-ScheduledTask -TaskName 'CourierWindowsWorker' -Confirm:$false "
        "-ErrorAction SilentlyContinue"
    )


def prove_live_uninstall(package: Path) -> dict:
    """Install the package where uninstall.ps1 looks, run it, report step 12.

    Refuses unless live_uninstall_permitted() is true. Does not call install.ps1.
    """
    if not live_uninstall_permitted():
        raise AssertionError("live uninstall is refused outside a GitHub Actions runner")
    if os.name != "nt":
        raise AssertionError("live uninstall is Windows-only")
    script = package / "uninstall.ps1"
    if not script.is_file():
        raise AssertionError(f"packaged uninstall.ps1 missing: {script}")
    assert_uninstall_preserves_user_data(script.read_text(encoding="utf-8"))

    admin = _powershell(
        "$p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent()); "
        "if ($p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { exit 0 } else { exit 3 }"
    )
    if admin.returncode != 0:
        raise AssertionError("live uninstall needs an Administrator runner; refusing to continue")

    profile = Path(os.environ["USERPROFILE"]).resolve()
    if profile.parent != Path(r"C:\Users"):
        raise AssertionError("USERPROFILE is not under C:\\Users, so uninstall.ps1 would not see this data")
    home = profile / "AppData" / "Local" / "Courier"
    install_dir = Path(os.environ["ProgramFiles"]) / "CourierWorker"
    db = home / "courier.db"
    log = home / "logs" / "courier.log"
    config = home / "config.json"
    run = home / "run"
    if db.exists() and not db.read_bytes().startswith(_JOURNAL_MARKER):
        raise AssertionError("refusing to overwrite an existing courier.db")
    if log.exists() and _LOG_MARKER not in log.read_text(encoding="utf-8", errors="replace"):
        raise AssertionError("refusing to overwrite an existing courier log")
    if config.exists() and _CONFIG_MARKER not in config.read_text(encoding="utf-8", errors="replace"):
        raise AssertionError("refusing to overwrite an existing config.json")

    try:
        if install_dir.exists():
            shutil.rmtree(install_dir)
        shutil.copytree(package, install_dir)
        registered = _powershell(
            "$ErrorActionPreference = 'Stop'; "
            "Import-Module ScheduledTasks; "
            "$action = New-ScheduledTaskAction -Execute (Join-Path $env:SystemRoot 'System32\\cmd.exe') "
            "-Argument '/c exit 0'; "
            "Register-ScheduledTask -TaskName 'CourierWindowsWorker' -Action $action -Force | Out-Null"
        )
        if registered.returncode != 0:
            raise AssertionError(
                "could not register CourierWindowsWorker\n"
                + registered.stdout[-2000:]
                + "\n"
                + registered.stderr[-2000:]
            )
        if _task_query().returncode != 0:
            raise AssertionError("CourierWindowsWorker was not visible to Get-ScheduledTask")

        (home / "logs").mkdir(parents=True, exist_ok=True)
        run.mkdir(parents=True, exist_ok=True)
        db.write_bytes(_JOURNAL_MARKER)
        log.write_text(_LOG_MARKER, encoding="utf-8")
        config.write_text(
            json.dumps({"COURIER_CONTROLLER_PORT": 9, "marker": _CONFIG_MARKER}),
            encoding="utf-8",
        )
        (run / "marker.txt").write_text("remove-me\n", encoding="utf-8")

        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            check=False,
            capture_output=True,
            text=True,
        )
        write_evidence(
            "uninstall-log.txt",
            (completed.stdout or "")[-4000:] + "\n" + (completed.stderr or "")[-4000:],
        )
        if completed.returncode != 0:
            raise AssertionError(f"uninstall.ps1 exited {completed.returncode}")
        return {
            "config_removed": not config.exists(),
            "courier_db_preserved": db.is_file() and db.read_bytes() == _JOURNAL_MARKER,
            "logs_preserved": log.is_file() and log.read_text(encoding="utf-8") == _LOG_MARKER,
            "program_dir_removed": not install_dir.exists(),
            "run_removed": not run.exists(),
            "task_removed": _task_query().returncode != 0,
        }
    finally:
        _cleanup_live_uninstall(home, install_dir)


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
    """Rule 0 step 10: rebuild of the journal matches the live projection."""
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
            break
        except sqlite3.OperationalError as exc:
            last_error = exc
            time.sleep(0.5)
    else:
        raise AssertionError(f"journal stayed locked during replay: {last_error}")
    assert report.ok, report
    assert copy_hash == live, (copy_hash, live)
    assert rebuilt_hash == live, (rebuilt_hash, live)
    return live


def _popen_launcher(launcher_exe: Path, env: dict, **kwargs):
    """Start Courier.exe. WinError 5 means the runner job forbids breakaway."""
    breakaway = subprocess.CREATE_NEW_PROCESS_GROUP | 0x01000000
    try:
        return subprocess.Popen([str(launcher_exe)], env=env, creationflags=breakaway, **kwargs)
    except PermissionError as exc:
        if getattr(exc, "winerror", None) == 5:
            return subprocess.Popen(
                [str(launcher_exe)],
                env=env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                **kwargs,
            )
        raise


def _assert_no_system_python(env: dict) -> None:
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "VIRTUAL_ENV", "COURIER_HOME"):
        if name in env:
            raise AssertionError(f"packaged launch env still has {name}")
    where = Path(env["PATH"].split(";")[0]) / "where.exe"
    probe = subprocess.run([str(where), "python"], env=env, capture_output=True, text=True, check=False)
    if probe.returncode == 0:
        raise AssertionError(f"system python is still visible: {probe.stdout}")


def _processes_under(package_dir: Path) -> list[str]:
    prefix = str(package_dir.resolve()).lower()
    if not prefix.endswith("\\"):
        prefix += "\\"
    found = []
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            exe = proc.info["exe"] or ""
            pid = proc.info["pid"]
            name = proc.info["name"] or ""
        except (psutil.Error, TypeError):
            continue
        if exe.lower().startswith(prefix):
            found.append(f"{pid} {name} {exe}")
    return found


def _assert_no_package_processes(package_dir: Path, timeout=15) -> None:
    """Rule 0 step 7 for the packaged tree: no executable under the package dir."""
    deadline = time.monotonic() + timeout
    offenders = _processes_under(package_dir)
    while offenders and time.monotonic() < deadline:
        time.sleep(0.25)
        offenders = _processes_under(package_dir)
    assert offenders == [], f"package processes still alive: {offenders}"


def _stop_package_processes(package_dir: Path) -> None:
    """Best-effort reap after the assertion, so a failed run does not lock the package."""
    for line in _processes_under(package_dir):
        pid = line.split()[0]
        subprocess.run(["taskkill", "/F", "/T", "/PID", pid], check=False)


@pytest.fixture
def _package_process_cleanup():
    """Reap packaged executables after the harness returns, including on failure."""
    yield
    if os.name != "nt":
        return
    try:
        package = packaged_root()
    except AssertionError:
        return
    if package is not None:
        _stop_package_processes(package)


def _process_snapshot(package_dir: Path | None) -> str:
    prefix = None
    if package_dir is not None:
        prefix = str(package_dir.resolve()).lower()
        if not prefix.endswith("\\"):
            prefix += "\\"
    rows = []
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            name = proc.info["name"] or ""
            exe = proc.info["exe"] or ""
            pid = proc.info["pid"]
        except (psutil.Error, TypeError):
            continue
        under = bool(prefix and exe.lower().startswith(prefix))
        if under or "courier" in name.lower() or name.lower().startswith("python"):
            rows.append(f"{pid}\t{name}\t{exe}")
    return "\n".join(rows) + ("\n" if rows else "")


def _copy_logs(courier_dir: Path) -> None:
    chunks = []
    for rel in ("crash.txt", "logs/controller.log", "logs/worker.log", "logs/hub.log"):
        path = courier_dir / rel
        chunks.append(f"----- {rel} -----")
        if path.is_file():
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
            chunks.append("\n".join(lines))
        else:
            chunks.append("(missing)")
    write_evidence("logs.txt", "\n".join(chunks) + "\n")


@pytest.mark.skipif(os.name != 'nt', reason="Windows specific clean-machine harness")
def test_win_clean_machine_harness(tmp_path, _package_process_cleanup):
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

    COURIER_HARNESS_PACKAGE_DIR selects the packaged artifact. That mode does
    not compile the repo launcher and does not put the checkout on PYTHONPATH.
    """
    package_dir = packaged_root()
    if package_dir is not None:
        launcher_exe = package_dir / "Courier.exe"
        embed = package_dir / "python" / "python.exe"
        assert launcher_exe.is_file(), f"packaged launcher missing: {launcher_exe}"
        assert embed.is_file(), f"embedded python missing: {embed}"
        env = package_child_env(tmp_path)
        _assert_no_system_python(env)
        ready_timeout = 90
    else:
        # Repo checkout: compile the launcher and let it import this tree.
        build_script = Path("scripts/windows_worker/launcher/build_launcher.ps1").resolve()
        if build_script.exists():
            subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(build_script)], check=True)
        launcher_exe = Path("scripts/windows_worker/Courier.exe").resolve()
        assert launcher_exe.exists(), "Courier.exe must be built before tests"
        env = os.environ.copy()
        env["LOCALAPPDATA"] = str(tmp_path)
        env["COURIER_TEST_NO_JOB"] = "1"
        env["PYTHONPATH"] = str(Path.cwd())
        ready_timeout = 30
    # Packaged runs use a high port pair so they do not collide with a
    # source-tree harness that still binds 8800/8801.
    controller_port = 18770 if package_dir is not None else 8800
    hub_port = 18771 if package_dir is not None else 8801
    courier_dir = tmp_path / "Courier"
    courier_dir.mkdir(parents=True)
    
    # Force specific ports via config.json to avoid conflicts
    config_file = courier_dir / "config.json"
    config_file.write_text(json.dumps({
        "COURIER_CONTROLLER_PORT": controller_port,
        "COURIER_HUB_PORT": hub_port
    }))

    owned_pids = []

    launcher = _popen_launcher(
        launcher_exe, env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )

    try:
        # Wait for token
        token_file = courier_dir / "run" / "controller.token"
        start_time = time.monotonic()
        while time.monotonic() - start_time < ready_timeout:
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

        controller_url = f"http://127.0.0.1:{controller_port}"
        hub_url = f"http://127.0.0.1:{hub_port}"

        def api(method, path, body=None):
            data = json.dumps(body).encode() if body is not None else None
            req = urllib.request.Request(controller_url + path, data=data, method=method,
                                         headers={"X-Courier-Token": token, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read() or b"{}")

        # Wait for Hub to be up
        start_time = time.monotonic()
        while time.monotonic() - start_time < ready_timeout:
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
    if package_dir is not None:
        _assert_no_package_processes(package_dir)
        write_evidence("processes-after-close.txt", _process_snapshot(package_dir))
    # Frozen journal after close replays to the same projection.
    _checkpoint_journal(courier_dir)
    close_hash = _assert_replay_matches_live(courier_dir, tmp_path / "replay-after-close")
    if package_dir is not None:
        write_evidence("hashes-after-close.txt", f"{close_hash}\n")

    # 4. Restart and Replay
    launcher2 = _popen_launcher(launcher_exe, env)
    restart_pids = []
    try:
        start_time = time.monotonic()
        while time.monotonic() - start_time < ready_timeout:
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
        restart_hash = _assert_replay_matches_live(courier_dir, tmp_path / "replay-after-restart")

    finally:
        restart_pids.extend(_courier_tree(launcher2.pid))
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(launcher2.pid)], check=False)
        launcher2.wait(10)

    _assert_no_orphan_courier_processes(courier_dir, restart_pids)
    if package_dir is not None:
        _assert_no_package_processes(package_dir)
        write_evidence("processes-after-restart.txt", _process_snapshot(package_dir))
        write_evidence(
            "hashes-after-restart.txt",
            f"after_close={close_hash}\nafter_restart={restart_hash}\nstep7=no-orphans\nstep10=replay-equals-live\n",
        )
        _copy_logs(courier_dir)

    # Rule 0 step 12 — the run produced the user data uninstall must keep.
    # The script itself is not executed here (see the module note).
    assert (courier_dir / "courier.db").is_file()
    assert (courier_dir / "logs").is_dir()
    assert (courier_dir / "config.json").is_file()
    assert (courier_dir / "run").is_dir()
    assert_uninstall_preserves_user_data(UNINSTALL_SCRIPT.read_text(encoding="utf-8"))
