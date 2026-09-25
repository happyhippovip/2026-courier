"""Deterministic tests for the Windows Antigravity startup/recovery authority.

Live Windows is not available in CI, so processes, ports, clock and the
Windows host (Task Scheduler / registry / startup folder) are faked.
"""

from __future__ import annotations

import io
import json
import logging
import sys
import tempfile
import unittest
import unittest.mock
import xml.etree.ElementTree as ET
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = TESTS_DIR.parent
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

from scripts.windows_antigravity import installer  # noqa: E402
from scripts.windows_antigravity import supervisor as sv  # noqa: E402

EXE = r"C:\Users\lol\AppData\Local\Programs\Antigravity\Antigravity.exe"
LS_EXE = r"C:\Users\lol\AppData\Local\Programs\Antigravity\resources\bin\language_server_windows_x64.exe"


class FakeBackend:
    """In-memory Windows: processes, listeners, clock.

    mode controls what a spawned Antigravity does:
      healthy  - main + renderer + language server listening on ls_port
      no_ls    - main + renderer only
      vanish   - the spawned process never shows up (launcher crash)
    """

    def __init__(self, mode: str = "healthy") -> None:
        self.mode = mode
        self.t = 1_000_000.0
        self.procs: dict[int, sv.ProcInfo] = {}
        self.ports: dict[int, set[int]] = {}
        self.unreachable: set[int] = set()
        self.next_pid = 5000
        self.spawned: list[list[str]] = []
        self.terminated: list[int] = []
        self.ls_port = 51000
        self.ui_port = 52000

    # helpers
    def add(self, pid, ppid, exe, cmdline=(), name=None, ports=()):
        self.procs[pid] = sv.ProcInfo(pid, ppid, name or exe.rsplit("\\", 1)[-1], exe, tuple(cmdline), self.t + pid / 1e6)
        if ports:
            self.ports[pid] = set(ports)
        return pid

    def launch(self, argv):
        pid = self.next_pid
        self.next_pid += 10
        self.add(pid, 4, argv[0], argv, ports=(self.ui_port,))
        self.add(pid + 1, pid, argv[0], [argv[0], "--type=renderer"])
        if self.mode == "healthy":
            self.add(pid + 2, pid + 1, LS_EXE, [LS_EXE], ports=(self.ls_port,))
        return pid

    # Backend protocol
    def list_processes(self):
        return list(self.procs.values())

    def listening_ports(self, pids):
        return {pid: set(p) for pid, p in self.ports.items() if pid in pids}

    def spawn(self, argv, minimized):
        self.spawned.append(list(argv))
        if self.mode == "vanish":
            pid = self.next_pid
            self.next_pid += 10
            return pid
        return self.launch(argv)

    def terminate_tree(self, pid, timeout):
        self.terminated.append(pid)
        for p in sv.descendants(pid, self.list_processes()):
            self.procs.pop(p.pid, None)
            self.ports.pop(p.pid, None)

    def kill(self, pid):
        for p in sv.descendants(pid, self.list_processes()):
            self.procs.pop(p.pid, None)
            self.ports.pop(p.pid, None)

    def tcp_probe(self, host, port, timeout=2.0):
        live = {p for s in self.ports.values() for p in s}
        return port in live and port not in self.unreachable

    def http_probe(self, url, timeout=5.0):
        return True

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds

    def advance(self, seconds):
        self.t += seconds


def make_cfg(**kw) -> sv.Config:
    base = dict(exe_path=EXE, startup_grace_seconds=60, unhealthy_checks_before_restart=3,
                backoff_initial_seconds=10, backoff_max_seconds=80,
                max_starts_per_window=3, start_window_seconds=3600)
    base.update(kw)
    return sv.Config(**base)


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name) / "home"
        self.home.mkdir()
        self.log_stream = io.StringIO()
        self.logger = logging.getLogger(f"test-{id(self)}")
        self.logger.handlers[:] = []
        handler = logging.StreamHandler(self.log_stream)
        handler.addFilter(sv.RedactingFilter())
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def sup(self, backend, cfg=None, dirs=()):
        return sv.Supervisor(cfg or make_cfg(), backend, self.home, self.logger,
                             exists=lambda p: p == EXE,
                             dir_exists=lambda p: p in dirs)


class SingletonAndDuplicates(Base):
    def test_starts_exactly_once_and_becomes_healthy(self):
        be = FakeBackend()
        s = self.sup(be)
        st = s.tick()
        self.assertEqual(st.status, sv.STATUS_STARTING)
        for _ in range(5):
            be.advance(30)
            st = s.tick()
        self.assertEqual(len(be.spawned), 1)
        self.assertEqual(st.status, sv.STATUS_HEALTHY)
        self.assertEqual(st.instances, 1)
        self.assertTrue(st.language_server_connected)
        self.assertEqual(st.ui_port, be.ls_port if be.ls_port < be.ui_port else be.ui_port)

    def test_running_instance_is_adopted_not_duplicated(self):
        be = FakeBackend()
        be.launch([EXE])
        s = self.sup(be)
        st = s.tick()
        self.assertEqual(be.spawned, [])
        self.assertEqual(st.status, sv.STATUS_HEALTHY)

    def test_no_second_spawn_while_starting(self):
        be = FakeBackend(mode="vanish")  # started process not visible yet
        s = self.sup(be)
        s.tick()
        for _ in range(5):
            be.advance(10)  # still inside 60 s grace
            st = s.tick()
        self.assertEqual(len(be.spawned), 1)
        self.assertEqual(st.status, sv.STATUS_STARTING)

    def test_electron_children_are_not_counted_as_instances(self):
        be = FakeBackend()
        main = be.launch([EXE])
        mains = sv.find_main_instances(be.list_processes(), EXE, None)
        self.assertEqual([m.pid for m in mains], [main])

    def test_orphaned_language_server_is_not_an_instance(self):
        be = FakeBackend()
        be.add(900, 1, EXE, [EXE, "--stdio"], name="language_server")  # parent died
        mains = sv.find_main_instances(be.list_processes(), EXE, None, sv.Config().language_server_pattern)
        self.assertEqual(mains, [])
        self.sup(be).tick()
        self.assertEqual(len(be.spawned), 1)

    def test_second_supervisor_is_rejected_by_lock(self):
        lock_path = self.home / "supervisor.lock"
        a, b = sv.SingletonLock(lock_path), sv.SingletonLock(lock_path)
        self.assertTrue(a.acquire())
        try:
            self.assertFalse(b.acquire())
            be = FakeBackend()
            rc = self.sup(be).run(b, max_ticks=3)
            self.assertEqual(rc, 0)
            self.assertEqual(be.spawned, [])  # rejected supervisor did nothing
        finally:
            a.release()
        self.assertTrue(b.acquire())
        b.release()

    def test_repeated_startup_is_idempotent(self):
        be = FakeBackend()
        for _ in range(4):  # e.g. logon trigger + 15-min repetition firing
            s = self.sup(be)
            s.run(sv.SingletonLock(self.home / "supervisor.lock"), max_ticks=3)
        self.assertEqual(len(be.spawned), 1)
        self.assertEqual(len(sv.find_main_instances(be.list_processes(), EXE, None)), 1)


class Recovery(Base):
    def test_dead_process_is_recovered(self):
        be = FakeBackend()
        s = self.sup(be)
        s.tick()
        be.advance(30)
        self.assertEqual(s.tick().status, sv.STATUS_HEALTHY)
        be.kill(s.state.main_pid)  # e.g. the midnight crash
        be.advance(30)
        st = s.tick()
        self.assertEqual(len(be.spawned), 2)
        self.assertEqual(st.status, sv.STATUS_STARTING)
        be.advance(30)
        self.assertEqual(s.tick().status, sv.STATUS_HEALTHY)

    def test_stale_pid_is_not_adopted(self):
        be = FakeBackend()
        be.add(4242, 1, r"C:\Windows\notepad.exe", [r"C:\Windows\notepad.exe"])  # PID reused
        sv.State(status=sv.STATUS_HEALTHY, main_pid=4242, main_create_time=1.0).save(self.home / "state.json")
        s = self.sup(be)
        st = s.tick()
        self.assertEqual(len(be.spawned), 1)
        self.assertNotEqual(st.main_pid, 4242)
        self.assertIn(4242, be.procs)  # unrelated process untouched

    def test_changing_port_is_followed_without_restart(self):
        be = FakeBackend()
        be.launch([EXE])
        s = self.sup(be, make_cfg(ui_port=be.ui_port))
        st = s.tick()
        self.assertEqual(st.ui_port, be.ui_port)
        main = st.main_pid
        be.ports[main] = {53123}  # UI moved to a new port after an update
        be.advance(30)
        st = s.tick()
        self.assertEqual(st.status, sv.STATUS_HEALTHY)
        self.assertIn(st.ui_port, {53123, be.ls_port})
        self.assertNotEqual(st.ui_port, be.ui_port)
        self.assertEqual(be.spawned, [])
        self.assertEqual(be.terminated, [])

    def test_missing_language_server_restarts_after_threshold(self):
        be = FakeBackend(mode="no_ls")
        be.launch([EXE])
        other = be.add(777, 1, r"C:\Tools\muse.exe", ["muse", "--yolo"])
        s = self.sup(be)
        for _ in range(2):
            st = s.tick()
            self.assertEqual(st.status, sv.STATUS_UNHEALTHY)
            be.advance(30)
        self.assertEqual(be.terminated, [])
        st = s.tick()  # third consecutive unhealthy check
        self.assertEqual(len(be.terminated), 1)
        self.assertEqual(len(be.spawned), 1)
        self.assertIn(other, be.procs)  # only the Antigravity tree was stopped
        self.assertFalse(st.language_server_running)

    def test_unreachable_language_server_counts_as_not_connected(self):
        be = FakeBackend()
        be.launch([EXE])
        be.unreachable.add(be.ls_port)
        st = self.sup(be).tick()
        self.assertTrue(st.language_server_running)
        self.assertFalse(st.language_server_connected)
        self.assertEqual(st.status, sv.STATUS_UNHEALTHY)

    def test_bounded_retry_with_backoff_then_gave_up(self):
        be = FakeBackend(mode="vanish")
        cfg = make_cfg(startup_grace_seconds=5)
        s = self.sup(be, cfg)
        spawn_times = []
        for _ in range(200):  # ~100 minutes
            n = len(be.spawned)
            st = s.tick()
            if len(be.spawned) > n:
                spawn_times.append(be.t)
            be.advance(30)
            if be.t - 1_000_000 > 3000:
                break
        self.assertEqual(len(be.spawned), cfg.max_starts_per_window)
        gaps = [b - a for a, b in zip(spawn_times, spawn_times[1:])]
        self.assertEqual(gaps, sorted(gaps))  # non-decreasing backoff
        self.assertEqual(st.status, sv.STATUS_GAVE_UP)

    def test_budget_refills_after_window(self):
        be = FakeBackend(mode="vanish")
        cfg = make_cfg(startup_grace_seconds=5, start_window_seconds=600)
        s = self.sup(be, cfg)
        for _ in range(15):  # 450 s: inside the 600 s window
            s.tick()
            be.advance(30)
        spent = len(be.spawned)
        self.assertEqual(spent, cfg.max_starts_per_window)
        be.mode = "healthy"
        be.advance(700)
        s.tick()
        self.assertEqual(len(be.spawned), spent + 1)

    def test_degraded_instance_kept_when_budget_spent(self):
        be = FakeBackend(mode="no_ls")
        cfg = make_cfg(max_starts_per_window=1, unhealthy_checks_before_restart=1)
        s = self.sup(be, cfg)
        s.tick()  # spawn #1 (budget now spent)
        for _ in range(10):
            be.advance(70)
            st = s.tick()
        self.assertEqual(len(be.spawned), 1)
        self.assertEqual(be.terminated, [])  # never killed without replacement
        self.assertEqual(st.status, sv.STATUS_GAVE_UP)


class ProfileAndSafety(Base):
    def test_existing_profile_is_passed_and_preserved(self):
        profile = Path(self._tmp.name) / "profile"
        profile.mkdir()
        (profile / "Cookies").write_bytes(b"session-data")
        before = sorted(p.name for p in profile.iterdir())
        be = FakeBackend()
        s = self.sup(be, make_cfg(user_data_dir=str(profile)), dirs={str(profile)})
        for _ in range(3):
            s.tick()
            be.advance(30)
        self.assertEqual(be.spawned[0], [EXE, f"--user-data-dir={profile}"])
        self.assertEqual(sorted(p.name for p in profile.iterdir()), before)
        self.assertEqual((profile / "Cookies").read_bytes(), b"session-data")

    def test_missing_profile_refuses_to_start(self):
        be = FakeBackend()
        missing = Path(self._tmp.name) / "gone"
        st = self.sup(be, make_cfg(user_data_dir=str(missing))).tick()
        self.assertEqual(st.status, sv.STATUS_CONFIG_ERROR)
        self.assertEqual(be.spawned, [])
        self.assertFalse(missing.exists())

    def test_other_profile_is_not_our_instance(self):
        be = FakeBackend()
        be.launch([EXE, r"--user-data-dir=C:\Users\lol\.gemini_alt"])
        s = self.sup(be)
        s.tick()
        self.assertEqual(len(be.spawned), 1)  # default profile started separately
        self.assertEqual(be.terminated, [])

    def test_missing_exe_is_config_error(self):
        be = FakeBackend()
        s = sv.Supervisor(make_cfg(), be, self.home, self.logger, exists=lambda p: False)
        st = s.tick()
        self.assertEqual(st.status, sv.STATUS_CONFIG_ERROR)
        self.assertEqual(be.spawned, [])

    def test_no_credential_logging(self):
        secret = "ya29.a0AfH6SMBxSECRETSECRETSECRET"
        be = FakeBackend()
        s = self.sup(be, make_cfg(extra_args=[f"--auth-token={secret}", "--oauth", f"Bearer {secret}"]))
        s.tick()
        self.assertTrue(be.spawned)  # args still passed to the process
        log = self.log_stream.getvalue()
        self.assertIn("starting Antigravity", log)
        self.assertNotIn(secret, log)
        self.assertNotIn(secret, (self.home / "state.json").read_text())
        for sample in (f"token={secret}", "api_key: AIzaSyA-1234567890abcdefghijklmnopqrstu",
                       "Authorization: Bearer abcdefghijklmnop", "ghp_" + "x" * 30):
            self.assertNotIn(sample.split()[-1].split("=")[-1], sv.redact(sample))

    def test_agent_probe_success_and_redaction(self):
        cfg = make_cfg(agent_probe_command=["agy", "-p", "Reply with exactly: AGENT_OK"], agent_probe_expect="AGENT_OK")

        def runner(argv, **kw):
            self.assertEqual(argv[0], "agy")
            return sv.subprocess.CompletedProcess(argv, 0, "AGENT_OK\ntoken=supersecretvalue123", "")

        ok, detail = sv.run_agent_probe(cfg, runner)
        self.assertTrue(ok)
        self.assertNotIn("supersecretvalue123", detail)

    def test_agent_probe_failure(self):
        cfg = make_cfg(agent_probe_command=["agy"], agent_probe_expect="AGENT_OK")
        ok, _ = sv.run_agent_probe(cfg, lambda argv, **kw: sv.subprocess.CompletedProcess(argv, 1, "", "auth required"))
        self.assertFalse(ok)
        self.assertFalse(sv.run_agent_probe(make_cfg(), lambda *a, **k: None)[0])

    def test_no_destructive_cleanup_of_home(self):
        (self.home / "notes.txt").write_text("keep me")
        be = FakeBackend(mode="no_ls")
        be.launch([EXE])
        s = self.sup(be)
        for _ in range(6):
            s.tick()
            be.advance(30)
        self.assertEqual((self.home / "notes.txt").read_text(), "keep me")
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), ["notes.txt", "state.json"])

    def test_config_rejects_unknown_keys_and_bad_backoff(self):
        with self.assertRaises(ValueError):
            sv.Config.from_dict({"exe_pth": "x"})
        with self.assertRaises(ValueError):
            sv.Config.from_dict({"backoff_initial_seconds": 100, "backoff_max_seconds": 10})
        cfg = sv.Config.from_dict({"_comment": "ok", "ui_port": 1234})
        self.assertEqual(cfg.ui_port, 1234)

    def test_example_config_loads(self):
        data = json.loads((COURIER_DIR / "scripts/windows_antigravity/config.example.json").read_text())
        cfg = sv.Config.from_dict(data)
        self.assertIsNone(cfg.user_data_dir)
        self.assertEqual(cfg.agent_probe_expect, "AGENT_OK")


class FakeHost:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.tasks = [
            {"name": "\\Antigravity watcher", "state": "Ready", "command": r"wscript.exe C:\Users\lol\agy\antigravity_watch.vbs"},
            {"name": "\\CourierMuseWall", "state": "Ready", "command": r"powershell -File C:\muse\wall.ps1 -StartAntigravity"},
            {"name": "\\CourierWindowsWorker", "state": "Ready", "command": r"C:\courier\start.bat"},
            {"name": "\\AntigravityUpdaterTask", "state": "Ready", "command": r"C:\ag\Antigravity.exe --update"},
        ]
        self.run_keys = {"Antigravity": f'"{EXE}"', "OneDrive": r"C:\OneDrive.exe /background"}
        self.startup = root / "Startup"
        self.startup.mkdir()
        (self.startup / "Antigravity.lnk").write_bytes(b"L\x00\x00\x00junk" + EXE.encode("utf-16-le"))
        (self.startup / "Spotify.lnk").write_bytes(b"L\x00\x00\x00spotify.exe")
        self.disabled: list[str] = []
        self.enabled: list[str] = []
        self.registered: list[str] = []
        self.started = 0
        self.deleted = 0

    def current_user(self):
        return "DESKTOP\\lol"

    def running_antigravity(self):
        return [{"exe": EXE, "cmdline": f'"{EXE}"'},
                {"exe": EXE, "cmdline": f'"{EXE}" --type=renderer'}]

    def scheduled_tasks(self):
        return [dict(t) for t in self.tasks]

    def disable_task(self, name):
        self.disabled.append(name)
        for t in self.tasks:
            if t["name"] == name:
                t["state"] = "Disabled"
        return True

    def enable_task(self, name):
        self.enabled.append(name)
        return True

    def run_values(self):
        return dict(self.run_keys)

    def delete_run_value(self, name):
        return self.run_keys.pop(name, None) is not None

    def set_run_value(self, name, value):
        self.run_keys[name] = value
        return True

    def startup_dirs(self):
        return [(self.startup, True)]

    def ensure_venv(self, venv):
        return venv / "Scripts" / "pythonw.exe"

    def register_task(self, xml, xml_path):
        self.registered.append(xml)
        return True

    def start_task(self):
        self.started += 1
        return True

    def delete_task(self):
        self.deleted += 1
        return True


class Installer(Base):
    def test_classification(self):
        c = installer.classify_authority
        self.assertEqual(c("Antigravity watcher", "wscript antigravity_watch.vbs"), installer.DUPLICATE)
        self.assertEqual(c("CourierMuseWall", "wall.ps1 -StartAntigravity"), installer.SHARED)
        self.assertIsNone(c("CourierWindowsWorker", "start.bat"))
        self.assertIsNone(c("AntigravityUpdater", "Antigravity.exe --update"))
        self.assertIsNone(c(sv.TASK_NAME, "pythonw supervisor.py run"))
        self.assertIsNone(c("x", r"C:\Users\lol\AppData\Local\CourierAntigravity\app\antigravity.py",
                            Path(r"C:\Users\lol\AppData\Local\CourierAntigravity")))

    def test_parse_user_data_dir(self):
        self.assertEqual(installer.parse_user_data_dir('"a.exe" --user-data-dir="C:\\p q\\x" --foo'), "C:\\p q\\x")
        self.assertEqual(installer.parse_user_data_dir("a.exe --user-data-dir C:\\x"), "C:\\x")
        self.assertIsNone(installer.parse_user_data_dir("a.exe"))

    def test_task_xml(self):
        xml = installer.build_task_xml("DESKTOP\\lol", r"C:\v\pythonw.exe", r"C:\a\supervisor.py", r"C:\a", "2026-09-25T09:00:00")
        root = ET.fromstring(xml.split("\n", 1)[1])
        ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
        self.assertEqual(root.find("t:Settings/t:MultipleInstancesPolicy", ns).text, "IgnoreNew")
        self.assertEqual(root.find("t:Settings/t:Hidden", ns).text, "true")
        self.assertEqual(root.find("t:Settings/t:ExecutionTimeLimit", ns).text, "PT0S")
        self.assertIsNotNone(root.find("t:Triggers/t:LogonTrigger", ns))
        self.assertEqual(root.find("t:Triggers/t:TimeTrigger/t:Repetition/t:Interval", ns).text, "PT15M")
        self.assertEqual(root.find("t:Principals/t:Principal/t:LogonType", ns).text, "InteractiveToken")
        self.assertTrue(root.find("t:Actions/t:Exec/t:Command", ns).text.endswith("pythonw.exe"))

    def test_install_is_idempotent_and_non_destructive(self):
        host = FakeHost(Path(self._tmp.name))
        out = io.StringIO()
        with unittest.mock.patch("sys.stdout", out):
            self.assertEqual(installer.install(self.home, host=host), 0)
        cfg = json.loads((self.home / "config.json").read_text())
        self.assertEqual(cfg["exe_path"], EXE)
        self.assertIsNone(cfg["user_data_dir"])  # default = signed-in profile
        self.assertEqual(host.disabled, ["\\Antigravity watcher"])
        self.assertNotIn("Antigravity", host.run_keys)
        self.assertIn("OneDrive", host.run_keys)
        self.assertFalse((host.startup / "Antigravity.lnk").exists())
        self.assertTrue((host.startup / "Spotify.lnk").exists())
        self.assertIn("KEPT (shared with Muse) task:\\CourierMuseWall", out.getvalue())
        self.assertTrue((self.home / "app" / "supervisor.py").exists())

        cfg["ui_port"] = 4321  # user edit must survive a re-install
        (self.home / "config.json").write_text(json.dumps(cfg))
        with unittest.mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(installer.install(self.home, host=host), 0)
        self.assertEqual(json.loads((self.home / "config.json").read_text())["ui_port"], 4321)
        self.assertEqual(host.disabled, ["\\Antigravity watcher"])  # not disabled twice
        self.assertEqual(len(installer.load_records(self.home)), 3)
        self.assertEqual(len(host.registered), 2)
        self.assertEqual(host.started, 2)

        with unittest.mock.patch("sys.stdout", io.StringIO()):
            installer.uninstall(self.home, restore=True, host=host)
        self.assertEqual(host.enabled, ["\\Antigravity watcher"])
        self.assertIn("Antigravity", host.run_keys)
        self.assertTrue((host.startup / "Antigravity.lnk").exists())
        self.assertEqual(installer.load_records(self.home), [])
        self.assertTrue((self.home / "config.json").exists())  # uninstall keeps config

    def test_keep_duplicates_only_reports(self):
        host = FakeHost(Path(self._tmp.name))
        with unittest.mock.patch("sys.stdout", io.StringIO()):
            installer.install(self.home, disable_duplicates=False, host=host)
        self.assertEqual(host.disabled, [])
        self.assertIn("Antigravity", host.run_keys)
        self.assertTrue((host.startup / "Antigravity.lnk").exists())

    def test_install_refuses_off_windows_without_host(self):
        if sv.IS_WINDOWS:
            self.skipTest("Windows host")
        with unittest.mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(installer.install(self.home), 2)



if __name__ == "__main__":
    unittest.main()
