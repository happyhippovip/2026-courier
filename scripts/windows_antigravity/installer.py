"""Install/uninstall the single Antigravity startup authority on Windows.

install (idempotent, safe to run any number of times):
  1. copies the supervisor into %LOCALAPPDATA%\\CourierAntigravity\\app so repo
     checkouts/branch switches never break login startup
  2. writes config.json only if none exists (seeded from the running
     Antigravity: its exe and --user-data-dir, i.e. the signed-in profile)
  3. creates a private venv with psutil
  4. disables (reversibly) other launchers that only start Antigravity;
     launchers that also start Muse are reported, never touched
  5. registers ONE Scheduled Task: at logon + every 15 min, hidden,
     MultipleInstancesPolicy=IgnoreNew, running pythonw (no console window)
  6. starts it once

Nothing here deletes a profile, a credential, or a log.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

try:
    from . import supervisor as sv
except ImportError:  # executed as a plain script from the app dir
    import supervisor as sv  # type: ignore[no-redef]

PKG_DIR = Path(__file__).resolve().parent
APP_FILES = ("supervisor.py", "installer.py", "__init__.py", "config.example.json")
DUPLICATE = "DUPLICATE"
SHARED = "SHARED"
RECORDS_FILE = "disabled_authorities.json"
CREATE_NO_WINDOW = 0x08000000


# --------------------------------------------------------------------------
# Pure logic (unit tested)
# --------------------------------------------------------------------------

def classify_authority(name: str, command: str, home: Path | None = None) -> str | None:
    """DUPLICATE = launches Antigravity and nothing we know of besides it.
    SHARED    = also drives Muse; reported only, never disabled.
    None      = unrelated, an updater, or our own authority."""
    text = f"{name} {command}".lower()
    if "antigravity" not in text:
        return None
    if sv.TASK_NAME.lower() in text:
        return None
    if home is not None and sv.norm_path(str(home)) in sv.norm_path(command):
        return None
    if re.search(r"updat", name.lower()):
        return None
    if "muse" in text:
        return SHARED
    return DUPLICATE


def parse_user_data_dir(cmdline: str) -> str | None:
    m = re.search(r'--user-data-dir(?:=|\s+)(?:"([^"]+)"|(\S+))', cmdline or "")
    if not m:
        return None
    return m.group(1) or m.group(2)


def seed_config(running: list[dict[str, str]], existing_exe: str | None) -> dict[str, Any]:
    """Initial config from the live Antigravity main process, if any."""
    cfg: dict[str, Any] = json.loads((PKG_DIR / "config.example.json").read_text(encoding="utf-8"))
    mains = [r for r in running if "--type=" not in (r.get("cmdline") or "")]
    if mains:
        main = mains[0]
        if main.get("exe"):
            cfg["exe_path"] = main["exe"]
        cfg["user_data_dir"] = parse_user_data_dir(main.get("cmdline") or "")
    elif existing_exe:
        cfg["exe_path"] = existing_exe
    return cfg


def build_task_xml(user: str, pythonw: str, script: str, workdir: str, start_boundary: str) -> str:
    """Task Scheduler 1.2 XML. IgnoreNew + the supervisor's own file lock make
    a second copy impossible; the 15-minute repetition revives a dead
    supervisor (e.g. after a midnight crash) without ever duplicating it."""
    u, py, sc, wd = (escape(x) for x in (user, pythonw, script, workdir))
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Courier: single startup/recovery authority for Google Antigravity</Description>
    <URI>\\{sv.TASK_NAME}</URI>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{u}</UserId>
      <Delay>PT20S</Delay>
    </LogonTrigger>
    <TimeTrigger>
      <Enabled>true</Enabled>
      <StartBoundary>{escape(start_boundary)}</StartBoundary>
      <Repetition>
        <Interval>PT15M</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
    </TimeTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{u}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>true</Hidden>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>5</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{py}</Command>
      <Arguments>"{sc}" run</Arguments>
      <WorkingDirectory>{wd}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def load_records(home: Path) -> list[dict[str, str]]:
    try:
        return json.loads((home / RECORDS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def save_records(home: Path, records: list[dict[str, str]]) -> None:
    (home / RECORDS_FILE).write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Side-effect boundary (faked in tests)
# --------------------------------------------------------------------------

class WindowsHost:
    def run(self, argv: list[str], **kw: Any) -> subprocess.CompletedProcess:
        kw.setdefault("capture_output", True)
        kw.setdefault("text", True)
        kw.setdefault("check", False)
        if sv.IS_WINDOWS:
            kw.setdefault("creationflags", CREATE_NO_WINDOW)
        return subprocess.run(argv, **kw)

    def _ps_json(self, script: str) -> list[dict[str, Any]]:
        proc = self.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                         script + " | ConvertTo-Json -Compress -Depth 3"])
        text = (proc.stdout or "").strip()
        if proc.returncode != 0 or not text:
            return []
        data = json.loads(text)
        return data if isinstance(data, list) else [data]

    def current_user(self) -> str:
        return f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}".lstrip("\\")

    def running_antigravity(self) -> list[dict[str, str]]:
        rows = self._ps_json("Get-CimInstance Win32_Process -Filter \"Name='Antigravity.exe'\" | "
                             "Select-Object @{n='exe';e={$_.ExecutablePath}},@{n='cmdline';e={$_.CommandLine}}")
        return [{"exe": r.get("exe") or "", "cmdline": r.get("cmdline") or ""} for r in rows]

    def scheduled_tasks(self) -> list[dict[str, str]]:
        rows = self._ps_json("Get-ScheduledTask | ForEach-Object { [pscustomobject]@{ "
                             "name = ($_.TaskPath + $_.TaskName); state = [string]$_.State; "
                             "command = (($_.Actions | ForEach-Object { \"$($_.Execute) $($_.Arguments)\" }) -join ' | ') } }")
        return [{"name": r.get("name") or "", "state": r.get("state") or "", "command": r.get("command") or ""} for r in rows]

    def disable_task(self, name: str) -> bool:
        return self.run(["schtasks", "/Change", "/TN", name, "/DISABLE"]).returncode == 0

    def enable_task(self, name: str) -> bool:
        return self.run(["schtasks", "/Change", "/TN", name, "/ENABLE"]).returncode == 0

    def run_values(self) -> dict[str, str]:
        import winreg  # noqa: PLC0415

        out = {}
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    out[name] = str(value)
                    i += 1
        except OSError:
            pass
        return out

    def delete_run_value(self, name: str) -> bool:
        import winreg  # noqa: PLC0415

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run",
                                0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
            return True
        except OSError:
            return False

    def set_run_value(self, name: str, value: str) -> bool:
        import winreg  # noqa: PLC0415

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run",
                                0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
            return True
        except OSError:
            return False

    def startup_dirs(self) -> list[tuple[Path, bool]]:
        dirs = []
        if os.environ.get("APPDATA"):
            dirs.append((Path(os.environ["APPDATA"]) / r"Microsoft\Windows\Start Menu\Programs\Startup", True))
        if os.environ.get("ProgramData"):
            dirs.append((Path(os.environ["ProgramData"]) / r"Microsoft\Windows\Start Menu\Programs\StartUp", False))
        return dirs

    def ensure_venv(self, venv: Path) -> Path:
        py = venv / "Scripts" / "python.exe"
        if not py.exists():
            self.run([sys.executable, "-m", "venv", str(venv)])
        if self.run([str(py), "-c", "import psutil"]).returncode != 0:
            self.run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-q", "psutil"])
        if self.run([str(py), "-c", "import psutil"]).returncode != 0:
            raise RuntimeError("psutil could not be installed into the supervisor venv")
        return venv / "Scripts" / "pythonw.exe"

    def register_task(self, xml: str, xml_path: Path) -> bool:
        xml_path.write_text(xml, encoding="utf-16")
        return self.run(["schtasks", "/Create", "/TN", sv.TASK_NAME, "/XML", str(xml_path), "/F"]).returncode == 0

    def start_task(self) -> bool:
        return self.run(["schtasks", "/Run", "/TN", sv.TASK_NAME]).returncode == 0

    def delete_task(self) -> bool:
        self.run(["schtasks", "/End", "/TN", sv.TASK_NAME])
        return self.run(["schtasks", "/Delete", "/TN", sv.TASK_NAME, "/F"]).returncode == 0


def _startup_file_text(path: Path) -> str:
    """Readable strings of a startup entry (.lnk stores its target inline)."""
    try:
        raw = path.read_bytes()[:65536]
    except OSError:
        return path.name
    return f"{path.name} {raw.decode('latin-1', 'ignore')} {raw.decode('utf-16-le', 'ignore')}"


# --------------------------------------------------------------------------
# Install / uninstall
# --------------------------------------------------------------------------

def scan_authorities(host: Any, home: Path) -> list[dict[str, Any]]:
    found = []
    for t in host.scheduled_tasks():
        verdict = classify_authority(t["name"].rsplit("\\", 1)[-1], t["command"], home)
        if verdict:
            found.append({"kind": "task", "name": t["name"], "state": t.get("state", ""), "verdict": verdict})
    for name, value in host.run_values().items():
        verdict = classify_authority(name, value, home)
        if verdict:
            found.append({"kind": "run", "name": name, "value": value, "verdict": verdict})
    for folder, writable in host.startup_dirs():
        if not folder.is_dir():
            continue
        for entry in sorted(folder.iterdir()):
            if entry.is_file():
                verdict = classify_authority(entry.stem, _startup_file_text(entry), home)
                if verdict:
                    found.append({"kind": "startup", "name": str(entry), "writable": writable, "verdict": verdict})
    return found


def disable_duplicate_authorities(host: Any, home: Path, found: list[dict[str, Any]]) -> list[str]:
    """Reversibly disable DUPLICATE launchers; returns report lines."""
    records = load_records(home)
    lines = []
    for item in found:
        label = f"{item['kind']}:{item['name']}"
        if item["verdict"] != DUPLICATE:
            lines.append(f"KEPT (shared with Muse) {label}")
            continue
        if item["kind"] == "task":
            if item.get("state", "").lower() == "disabled":
                lines.append(f"ALREADY_DISABLED {label}")
                continue
            ok = host.disable_task(item["name"])
            if ok:
                records.append({"kind": "task", "name": item["name"]})
        elif item["kind"] == "run":
            records.append({"kind": "run", "name": item["name"], "value": item["value"]})
            save_records(home, records)  # persist before deleting so it is restorable
            ok = host.delete_run_value(item["name"])
            if not ok:
                records.pop()
        else:
            if not item.get("writable"):
                lines.append(f"REPORT_ONLY (needs admin) {label}")
                continue
            dest_dir = home / "disabled_startup"
            dest_dir.mkdir(parents=True, exist_ok=True)
            src = Path(item["name"])
            dest = dest_dir / src.name
            try:
                shutil.move(str(src), str(dest))
                records.append({"kind": "startup", "name": str(src), "moved_to": str(dest)})
                ok = True
            except OSError:
                ok = False
        save_records(home, records)
        lines.append(f"{'DISABLED' if ok else 'COULD_NOT_DISABLE'} {label}")
    return lines


def restore_duplicates(host: Any, home: Path) -> list[str]:
    lines, remaining = [], []
    for rec in load_records(home):
        if rec["kind"] == "task":
            ok = host.enable_task(rec["name"])
        elif rec["kind"] == "run":
            ok = host.set_run_value(rec["name"], rec["value"])
        else:
            try:
                shutil.move(rec["moved_to"], rec["name"])
                ok = True
            except OSError:
                ok = False
        lines.append(f"{'RESTORED' if ok else 'COULD_NOT_RESTORE'} {rec['kind']}:{rec['name']}")
        if not ok:
            remaining.append(rec)
    save_records(home, remaining)
    return lines


def install(home: Path, disable_duplicates: bool = True, start: bool = True, host: Any = None) -> int:
    if host is None:
        if not sv.IS_WINDOWS:
            print("INSTALL=NO (Windows only)")
            return 2
        host = WindowsHost()
    home.mkdir(parents=True, exist_ok=True)
    app = home / "app"
    app.mkdir(parents=True, exist_ok=True)
    for name in APP_FILES:
        src = PKG_DIR / name
        if src.exists() and src.resolve() != (app / name).resolve():
            shutil.copy2(src, app / name)

    cfg_path = home / "config.json"
    if not cfg_path.exists():
        cfg = seed_config(host.running_antigravity(), sv.Config().resolved_exe())
        cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        print(f"CONFIG=created {cfg_path}")
    else:
        print(f"CONFIG=kept {cfg_path}")
    sv.load_config(cfg_path)  # fail fast on a broken config

    pythonw = host.ensure_venv(home / "venv")

    found = scan_authorities(host, home)
    if disable_duplicates:
        for line in disable_duplicate_authorities(host, home, found):
            print(line)
    else:
        for item in found:
            print(f"FOUND {item['verdict']} {item['kind']}:{item['name']}")

    start_boundary = dt.datetime.now().replace(second=0, microsecond=0).isoformat()
    xml = build_task_xml(host.current_user(), str(pythonw), str(app / "supervisor.py"), str(app), start_boundary)
    if not host.register_task(xml, home / "task.xml"):
        print("STARTUP_AUTHORITY=FAILED (schtasks /Create)")
        return 1
    print(f"STARTUP_AUTHORITY=ScheduledTask \\{sv.TASK_NAME} (logon + every 15 min, IgnoreNew)")
    if start:
        print(f"STARTED={'YES' if host.start_task() else 'NO'}")
    return 0


def uninstall(home: Path, restore: bool = False, host: Any = None) -> int:
    if host is None:
        if not sv.IS_WINDOWS:
            print("UNINSTALL=NO (Windows only)")
            return 2
        host = WindowsHost()
    print(f"TASK_REMOVED={'YES' if host.delete_task() else 'NO'}")
    if restore:
        for line in restore_duplicates(host, home):
            print(line)
    return 0
