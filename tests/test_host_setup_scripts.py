"""Contract tests for the one-line host setup scripts.

Static checks run everywhere. The dynamic runs use a fake HOME, stub macOS or
Windows tools and a local fixture repository, so they never touch the real
machine; they need bash (and pwsh for the Windows script) and are skipped on
Windows runners, where a CI account is an administrator.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SH = ROOT / "scripts/setup/courier-setup.sh"
PS1 = ROOT / "scripts/setup/courier-setup.ps1"
DOC = ROOT / "docs/HOST_SETUP.md"

BASH = shutil.which("bash")
GIT = shutil.which("git")
PWSH = shutil.which("pwsh")
POSIX = sys.platform != "win32"


def code_lines(path: Path) -> list[str]:
    """Script lines without whole-line comments."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#"):
            continue
        out.append(line)
    return out


FORBIDDEN_COMMON = [
    r"\bsudo\b",
    r"\bdoas\b",
    r"\bicacls\b",
    r"\btakeown\b",
    r"\bchown\b",
    r"\bchmod\b",
    r"\brm\s+-[a-zA-Z]*[rf]",
    r"\brm\s",
    r"\bkill\b",
    r"\bkillall\b",
    r"\bpkill\b",
    r"\btaskkill\b",
    r"Stop-Process",
    r"reset\s+--hard",
    r"\bgit\b.*\bclean\b",
    r"\bstash\b",
    r"--yolo",
    r"skip-permissions",
    r"dangerously",
    r"disable-sandbox",
    r"Set-MpPreference",
    r"Add-MpPreference",
    r"\breg(\.exe)?\s+(delete|add)\b",
    r"Remove-ItemProperty",
    r"Set-ItemProperty",
    r"Set-Acl",
    r"Set-ExecutionPolicy",
    r"-Verb\s+RunAs",
    r"\bnetsh\b",
    r"NetFirewall",
    r"\bspctl\b",
    r"\bcsrutil\b",
    r"\btccutil\b",
    r"Start-ScheduledTask",
    r"launchctl\s+(start|kickstart)",
    r"Remove-Item",
    r"\b(e|f)?grep\b",
    r"\brg\b",
]


@pytest.mark.parametrize("script", [SH, PS1], ids=["sh", "ps1"])
def test_no_forbidden_commands(script):
    hits = []
    for line in code_lines(script):
        for pat in FORBIDDEN_COMMON:
            if re.search(pat, line):
                hits.append((pat, line.strip()))
    assert not hits, hits


@pytest.mark.parametrize("script", [SH, PS1, DOC], ids=["sh", "ps1", "doc"])
def test_neutral_public_wording(script):
    text = script.read_text(encoding="utf-8").lower()
    for word in ("patent", "claim", "moat", "schutzpaket"):
        assert word not in text, word


@pytest.mark.parametrize("script", [SH, PS1], ids=["sh", "ps1"])
def test_scripts_are_ascii(script):
    # "irm | iex" on Windows PowerShell 5.1 may decode without a charset.
    script.read_bytes().decode("ascii")


def test_protected_folders_only_named_in_guard():
    for script, guard in ((SH, "cs_is_protected_path"), (PS1, "Test-ProtectedPath")):
        text = script.read_text(encoding="utf-8")
        start = text.index(guard)
        body_end = text.index("\n}", start) if script is SH else text.index("\n    }", start)
        outside = text[:start] + text[body_end:]
        for name in ("Desktop", "Documents", "Downloads"):
            assert name not in "\n".join(
                line for line in outside.splitlines() if not line.lstrip().startswith("#")
            ), (script.name, name)


def test_sh_is_pipe_safe():
    lines = code_lines(SH)
    text = "\n".join(lines)
    assert '"$0"' not in text and "${0" not in text and "BASH_SOURCE" not in text
    tail = [line for line in lines if line.strip()][-2:]
    assert tail == ['courier_setup_main "$@"', "exit $?"]
    assert "exec </dev/null" in text


@pytest.mark.skipif(not (POSIX and BASH), reason="needs bash on a POSIX host")
def test_sh_body_has_no_side_effects_before_final_call(tmp_path):
    # Everything except the last two lines only defines; nothing runs until the
    # whole script has arrived through the pipe.
    lines = SH.read_text(encoding="utf-8").rstrip("\n").splitlines()
    body = "\n".join(lines[:-2]) + "\ndeclare -F courier_setup_main >/dev/null && echo DEFINED\n"
    r = subprocess.run([BASH, "-s"], input=body, env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0 and r.stdout == "DEFINED\n" and r.stderr == "", (r.stdout, r.stderr)
    assert list(tmp_path.iterdir()) == []


def test_ps1_is_pipe_safe():
    lines = code_lines(PS1)
    text = "\n".join(lines)
    assert "$PSScriptRoot" not in text and "$PSCommandPath" not in text
    exits = [line.strip() for line in lines if re.search(r"(^|[{;])\s*exit\b", line)]
    assert exits == ["if ($MyInvocation.MyCommand.CommandType -eq 'ExternalScript') { exit $courierCode }"]
    assert "COURIER_SETUP_ARGS" in text
    # The error preference is set inside the function, not for the caller's session.
    first_pref = text.index("$ErrorActionPreference")
    assert first_pref > text.index("function Invoke-CourierSetup")


def test_ps1_service_only_through_user_level_installer():
    text = PS1.read_text(encoding="utf-8")
    assert "install_service.ps1" in text
    assert "RunLevel Limited" in text and "'\"SYSTEM\"'" in text
    assert "Register-ScheduledTask" not in text
    # Unregister appears once, inside the uninstall path.
    assert text.count("Unregister-ScheduledTask") == 1
    assert text.index("Unregister-ScheduledTask") > text.index("function Invoke-Uninstall")


def test_sh_service_only_through_no_start_installer():
    text = SH.read_text(encoding="utf-8")
    assert "COURIER_NO_START=1" in text
    assert "launchctl load" not in text and "launchctl unload" not in text
    assert "scripts/mac_worker/install.sh" in text


def test_writes_are_guarded_by_mode():
    sh = SH.read_text(encoding="utf-8")
    assert 'if [ "$CS_MODE" != "check" ] && command -v pbcopy' in sh
    assert 'if [ "$CS_MODE" != "check" ] && [ -d "$CS_BASE" ]; then' in sh
    ps = PS1.read_text(encoding="utf-8")
    assert "if ($Mode -ne 'check') {\n        try { Set-Clipboard" in ps
    assert "if ($Mode -eq 'check') { return }" in ps  # prerequisites


def test_doc_one_liners_match_branch():
    doc = DOC.read_text(encoding="utf-8")
    raw = "https://raw.githubusercontent.com/happyhippovip/2026-courier/lane/L6-host-setup/scripts/setup"
    assert f"curl -fsSL {raw}/courier-setup.sh | bash" in doc
    assert f"irm {raw}/courier-setup.ps1 | iex" in doc
    assert f"curl -fsSL {raw}/courier-setup.sh | bash" in SH.read_text(encoding="utf-8")
    assert f"irm {raw}/courier-setup.ps1 | iex" in PS1.read_text(encoding="utf-8")


def test_bash_syntax():
    if not (POSIX and BASH):
        pytest.skip("bash not available on a POSIX host")
    r = subprocess.run([BASH, "-n", str(SH)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_shellcheck_clean():
    sc = shutil.which("shellcheck")
    if not (POSIX and sc):
        pytest.skip("shellcheck not installed")
    r = subprocess.run([sc, "-s", "bash", str(SH)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


def test_ps1_parses():
    if not PWSH:
        pytest.skip("pwsh not installed")
    cmd = (
        "$e=$null;$t=$null;"
        f"[void][System.Management.Automation.Language.Parser]::ParseFile('{PS1}',[ref]$t,[ref]$e);"
        "if($e){$e|%{$_.ToString()};exit 1}"
    )
    r = subprocess.run([PWSH, "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


# --------------------------------------------------------------------------
# Dynamic runs (fake HOME, stub tools, local fixture repository)

needs_posix_bash = pytest.mark.skipif(not (POSIX and BASH and GIT), reason="needs bash and git on a POSIX host")

USER = "zedtester"
HOSTNAME = "zedtester-mbp.local"
LEAKY_MUSE = "muse 2.4.1 mail zed@example.com tok ghp_abcdefghijklmnop12"


def _write_exec(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _git(*args, cwd=None):
    subprocess.run(
        [GIT, "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
        cwd=cwd, check=True, capture_output=True,
    )


# Contract stub of a mac installer with the no-start mode the setup requires:
# COURIER_NO_START=1 writes the job with RunAtLoad/KeepAlive false and loads it.
NO_START_INSTALLER = """#!/bin/bash
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$(cd "$HERE/../.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.courier.mac_worker.plist"
[ "${COURIER_NO_START:-0}" = "1" ] || exit 9
launchctl list com.courier.mac_worker >/dev/null 2>&1 && exit 3
mkdir -p "$HOME/Library/LaunchAgents"
printf '<key>RunAtLoad</key>\\n<false/>\\n<key>KeepAlive</key>\\n<false/>\\n<string>%s</string>\\n<string>%s</string>\\n' \\
  "$TARGET_DIR" "${PYTHON_BIN:-${COURIER_PYTHON:-}}" > "$PLIST"
launchctl load "$PLIST"
"""


def _make_repo(tmp_path, name, files):
    src = tmp_path / f"{name}-src"
    for rel, body in files.items():
        p = src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    _git("init", "-q", "-b", "integration/v1", cwd=src)
    _git("add", "-A", cwd=src)
    _git("commit", "-qm", "init", cwd=src)
    bare = tmp_path / f"{name}.git"
    _git("clone", "-q", "--bare", str(src), str(bare))
    return bare


@pytest.fixture()
def fixture_repo(tmp_path):
    return _make_repo(tmp_path, "fixture", {
        "README.md": "fixture\n",
        "scripts/mac_worker/install.sh": NO_START_INSTALLER,
        "scripts/mac_worker/uninstall.sh": (ROOT / "scripts/mac_worker/uninstall.sh").read_text(),
    })


@pytest.fixture()
def mac_env(tmp_path, fixture_repo):
    home = tmp_path / "home"
    home.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stubs = {
        "sw_vers": "#!/bin/sh\necho 14.6.1\n",
        "sysctl": (
            "#!/bin/sh\ncase \"$2\" in\n"
            " machdep.cpu.brand_string) echo 'Apple M2';;\n hw.ncpu) echo 8;;\n hw.memsize) echo 17179869184;;\n"
            " vm.swapusage) echo \"total = 3072.00M  used = 2500.25M  free = 571.75M  (encrypted)\";;\n"
            " hw.pagesize) echo \"${COURIER_SETUP_PAGESIZE:-4096}\";;\n"
            " *) exit 1;;\nesac\n"
        ),
        "memory_pressure": "#!/bin/sh\necho 'System-wide memory free percentage: 40%'\n",
        "launchctl": (
            "#!/bin/sh\nst=\"$HOME/.lc_loaded\"\n"
            "case \"$1\" in\n"
            " list) [ -f \"$st\" ] || exit 1; if [ -f \"$HOME/.lc_running\" ]; then echo '\t\"PID\" = 4242;'; fi; exit 0;;\n"
            " *) echo \"$*\" >> \"$HOME/.lc_log\"; [ \"$1\" = load ] && : > \"$st\";;\nesac\nexit 0\n"
        ),
        "pbcopy": "#!/bin/sh\ncat > \"$HOME/.clipboard\"\n",
        "xcode-select": "#!/bin/sh\necho /Library/Developer/CommandLineTools\n",
        "hostname": f"#!/bin/sh\necho {HOSTNAME}\n",
        "scutil": f"#!/bin/sh\necho '{USER} MacBook'\n",
        "muse": f"#!/bin/sh\necho '{LEAKY_MUSE}'\n",
        "gh": "#!/bin/sh\nexit 1\n",
        "python3.12": "#!/bin/sh\necho 'Python 3.12.7'\n",
    }
    for name, body in stubs.items():
        _write_exec(bindir / name, body)
    env = {
        "HOME": str(home),
        "USER": USER,
        "PATH": f"{bindir}:/usr/bin:/bin",
        "COURIER_SETUP_UNAME": "Darwin",
        "COURIER_REPO_URL": fixture_repo.as_uri(),
        "LC_ALL": "C",
    }
    return home, env


def run_sh(env, *args, pipe=True):
    if pipe:
        cmd = [BASH, "-c", 'bash -s -- "$@" < "$SCRIPT"', "_", *args]
        env = {**env, "SCRIPT": str(SH)}
    else:
        cmd = [BASH, str(SH), *args]
    return subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)


def snapshot(root: Path) -> dict[str, tuple[int, float]]:
    out = {}
    for p in sorted(root.rglob("*")):
        st = p.lstat()
        out[str(p.relative_to(root))] = (st.st_size, st.st_mtime)
    return out


@needs_posix_bash
def test_sh_refuses_non_mac_without_changes(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "COURIER_SETUP_UNAME": "Linux"}
    r = run_sh(env, "--check")
    assert r.returncode == 3
    assert "HOST BLOCKED" in r.stderr and "macOS" in r.stderr
    assert list(home.iterdir()) == []


@needs_posix_bash
def test_sh_check_mode_writes_nothing(mac_env):
    home, env = mac_env
    before = snapshot(home)
    r = run_sh(env, "--check")
    assert r.returncode in (0, 2), r.stderr
    assert "HOST PARTIAL" in r.stdout and "WOULD_CLONE" in r.stdout
    assert snapshot(home) == before
    assert not (home / "Courier").exists()


@needs_posix_bash
def test_sh_setup_is_idempotent_and_redacted(mac_env):
    home, env = mac_env
    r = run_sh(env)
    assert r.returncode == 0, r.stdout + r.stderr
    report = (home / "Courier/setup-report.txt").read_text()
    clip = (home / ".clipboard").read_text()
    for text in (report, clip, r.stdout, r.stderr):
        assert USER not in text
        assert str(home) not in text
        assert "zedtester" not in text and "mbp" not in text
        assert "ghp_" not in text and "@example.com" not in text
    assert "HOST READY" in report
    assert "host_id: h-" in report
    assert "admission: PARKED (swap free 571 MB < 1024 MB), max heavy builders 1" in report
    assert "heavy_workers_started: 0" in report
    cfg = (home / "Courier/host-config.json").read_text()
    assert '"max_heavy_builders": 1' in cfg and str(home) not in cfg
    plist = (home / "Library/LaunchAgents/com.courier.mac_worker.plist").read_text()
    assert "<true/>" not in plist and str(home / "Courier/2026-courier") in plist
    log = (home / ".lc_log").read_text()
    assert "unload" not in log and "start" not in log

    r2 = run_sh(env, pipe=False)
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert "[UP_TO_DATE]" in r2.stdout
    assert "REGISTERED (already loaded; left as is)" in r2.stdout
    assert sorted(p.name for p in (home / "Courier").iterdir()) == [
        "2026-courier", "host-config.json", "setup-report.txt"]


@needs_posix_bash
def test_sh_dirty_checkout_untouched_sibling_used(mac_env):
    home, env = mac_env
    assert run_sh(env).returncode == 0
    scratch = home / "Courier/2026-courier/local-note.txt"
    scratch.write_text("keep me\n")
    r = run_sh(env)
    assert "2026-courier: DIRTY; left untouched" in r.stdout
    assert "[CLONED]" in r.stdout and "2026-courier-host" in r.stdout
    assert scratch.read_text() == "keep me\n"
    assert "dirty_worktrees: 1" in r.stdout


@needs_posix_bash
def test_sh_foreign_files_not_overwritten(mac_env):
    home, env = mac_env
    (home / "Courier").mkdir()
    (home / "Courier/host-config.json").write_text('{"owner": "someone else"}\n')
    r = run_sh(env)
    assert r.returncode == 2
    assert (home / "Courier/host-config.json").read_text() == '{"owner": "someone else"}\n'
    assert "was not written by courier-setup" in r.stdout


@needs_posix_bash
def test_sh_uninstall_refuses_running_worker(mac_env):
    home, env = mac_env
    assert run_sh(env).returncode == 0
    (home / ".lc_running").write_text("")
    r = run_sh(env, "--uninstall")
    assert r.returncode == 3
    assert "RUNNING (not removed" in r.stdout
    assert (home / "Library/LaunchAgents/com.courier.mac_worker.plist").exists()


@needs_posix_bash
def test_sh_skips_installer_that_would_start_worker(mac_env, tmp_path):
    home, env = mac_env
    # The trunk installer loads the job with RunAtLoad/KeepAlive and starts it.
    bare = _make_repo(tmp_path, "trunkish", {
        "scripts/mac_worker/install.sh": (ROOT / "scripts/mac_worker/install.sh").read_text(),
    })
    r = run_sh({**env, "COURIER_REPO_URL": bare.as_uri()})
    assert r.returncode == 2, r.stdout + r.stderr
    assert "installer in this checkout would start the worker" in r.stdout
    assert not (home / "Library/LaunchAgents").exists()
    assert not (home / ".lc_log").exists()


@needs_posix_bash
def test_sh_rejects_unknown_and_conflicting_flags(mac_env):
    _, env = mac_env
    assert run_sh(env, "--bogus").returncode == 64
    assert run_sh(env, "--check", "--uninstall").returncode == 64


# 100000 + 200000 + 100000 pages. 4096 bytes -> 1562 MB; 16384 bytes -> 6250 MB.
_VMSTAT_PAGES = (100000, 200000, 100000)


def _vmstat_text(page_size, header=True):
    free, inactive, speculative = _VMSTAT_PAGES
    if header:
        head = f"Mach Virtual Memory Statistics: (page size of {page_size} bytes)"
    else:
        head = "Mach Virtual Memory Statistics:"
    return (
        f"{head}\n"
        f"Pages free:                                {free}.\n"
        f"Pages active:                              10.\n"
        f"Pages inactive:                            {inactive}.\n"
        f"Pages speculative:                         {speculative}.\n"
        f"Pages wired down:                          10.\n"
        f"Pages occupied by compressor:              10.\n"
    )


_ZERO_SWAP = "total = 0.00M  used = 0.00M  free = 0.00M"


@pytest.mark.parametrize(
    ("fixture", "total", "free", "admission"),
    [
        (
            "total = 2048.00M  used = 1024.50M  free = 1023.50M  (encrypted)",
            "2048",
            "1023",
            "admission: PARKED (swap free 1023 MB < 1024 MB)",
        ),
        (
            "total = 8.00G  used = 6.50G  free = 1.50G  (encrypted)",
            "8192",
            "1536",
            "admission: OPEN",
        ),
        (
            _ZERO_SWAP,
            "0",
            "0",
            "admission: OPEN",
        ),
        (
            "total = 2048,00M  used = 1024,50M  free = 1023,50M  (encrypted)",
            "2048",
            "1023",
            "admission: PARKED (swap free 1023 MB < 1024 MB)",
        ),
        (
            "total = 2048.00K  used = 512.00K  free = 1536.00K",
            "2",
            "1",
            "admission: PARKED (swap free 1 MB < 1024 MB)",
        ),
    ],
)
@needs_posix_bash
def test_sh_swapusage_formats(mac_env, fixture, total, free, admission):
    _, env = mac_env
    r = run_sh({**env, "COURIER_SETUP_SWAPUSAGE_FIXTURE": fixture}, "--check")
    assert r.returncode in (0, 2), r.stdout + r.stderr
    assert f"swap_mb: total {total}, free {free}" in r.stdout
    assert admission in r.stdout
    assert "swap metric unreadable" not in r.stdout
    assert "metrics unreadable" not in r.stdout


@needs_posix_bash
def test_sh_swapusage_sysctl_failure_fails_closed(mac_env):
    _, env = mac_env
    r = run_sh({**env, "COURIER_SETUP_SWAPUSAGE_FIXTURE": "FAIL"}, "--check")
    assert r.returncode in (0, 2), r.stdout + r.stderr
    assert "swap_mb: total unknown, free unknown" in r.stdout
    assert "swap metric unreadable: sysctl vm.swapusage failed" in r.stdout
    assert "admission: PARKED (swap metric unreadable: sysctl vm.swapusage failed)" in r.stdout


@needs_posix_bash
def test_sh_swapusage_garbage_fails_closed(mac_env):
    _, env = mac_env
    r = run_sh({**env, "COURIER_SETUP_SWAPUSAGE_FIXTURE": "not a swapusage line"}, "--check")
    assert r.returncode in (0, 2), r.stdout + r.stderr
    assert "swap_mb: total unknown, free unknown" in r.stdout
    assert "admission: PARKED (swap metric unreadable: vm.swapusage not parsed)" in r.stdout
    assert "sysctl vm.swapusage failed" not in r.stdout


@pytest.mark.parametrize(
    ("page_size", "free_mb", "admission"),
    [
        (4096, 1562, "admission: PARKED (free RAM 1562 MB < 2048 MB)"),
        (16384, 6250, "admission: OPEN"),
    ],
)
@needs_posix_bash
def test_sh_vm_stat_uses_header_page_size(mac_env, page_size, free_mb, admission):
    _, env = mac_env
    r = run_sh({
        **env,
        "COURIER_SETUP_SWAPUSAGE_FIXTURE": _ZERO_SWAP,
        "COURIER_SETUP_VMSTAT_FIXTURE": _vmstat_text(page_size),
    }, "--check")
    assert r.returncode in (0, 2), r.stdout + r.stderr
    assert f"ram_mb: total 16384, free {free_mb}" in r.stdout
    assert "swap_mb: total 0, free 0" in r.stdout
    assert admission in r.stdout
    assert "swap metric unreadable" not in r.stdout


@needs_posix_bash
def test_sh_vm_stat_pagesize_falls_back_to_sysctl(mac_env):
    _, env = mac_env
    r = run_sh({
        **env,
        "COURIER_SETUP_SWAPUSAGE_FIXTURE": _ZERO_SWAP,
        "COURIER_SETUP_VMSTAT_FIXTURE": _vmstat_text(None, header=False),
        "COURIER_SETUP_PAGESIZE": "16384",
    }, "--check")
    assert r.returncode in (0, 2), r.stdout + r.stderr
    # Same page counts as the header test. 16384 from hw.pagesize, not a
    # hardcoded 4096 (that would be 1562 MB and would park).
    assert "ram_mb: total 16384, free 6250" in r.stdout
    assert "admission: OPEN" in r.stdout


def test_sh_probes_name_absolute_macos_tools():
    text = SH.read_text(encoding="utf-8")
    assert "/usr/sbin/sysctl" in text
    assert "/usr/bin/vm_stat" in text
    assert "hw.pagesize" in text
    assert "LC_ALL=C" in text
    assert "COURIER_SETUP_SWAPUSAGE_FIXTURE" in text


# ---- Windows script under pwsh with stubbed cmdlets -------------------------

needs_pwsh = pytest.mark.skipif(not (POSIX and PWSH and GIT), reason="needs pwsh and git on a POSIX host")

PS_STUBS = r"""
function global:Get-CimInstance { param($ClassName, $ErrorAction)
  switch ($ClassName) {
    'Win32_OperatingSystem' { [pscustomobject]@{Caption='Microsoft Windows 11 Pro'; Version='10.0.26100'; TotalVisibleMemorySize=16700000; FreePhysicalMemory=5200000} }
    'Win32_Processor' { [pscustomobject]@{Name='Test CPU'; NumberOfLogicalProcessors=16} }
    'Win32_PageFileUsage' { [pscustomobject]@{AllocatedBaseSize=4096; CurrentUsage=3584} }
    'Win32_Process' { @() }
  } }
function global:Get-ScheduledTask { param($TaskName, $ErrorAction)
  if (Test-Path (Join-Path $env:USERPROFILE 'registered.txt')) { [pscustomobject]@{State='Ready'; Principal=[pscustomobject]@{UserId="$env:COMPUTERNAME\$env:USERNAME"}} } }
function global:Set-Clipboard { param($Value, $ErrorAction) Set-Content -Path (Join-Path $env:USERPROFILE 'clip.txt') -Value $Value }
"""

PS_INSTALLER_STUB = """# stub of the user-level contract: RunLevel Limited, param InstallDir
param([string]$TaskName = "CourierWindowsWorker", [string]$InstallDir = "")
Set-Content -Path (Join-Path $env:USERPROFILE 'registered.txt') -Value "ok"
exit 0
"""


@pytest.fixture()
def win_env(tmp_path):
    src = tmp_path / "wsrc"
    (src / "scripts/windows_worker").mkdir(parents=True)
    (src / "scripts/windows_worker/install_service.ps1").write_text(PS_INSTALLER_STUB)
    _git("init", "-q", "-b", "integration/v1", cwd=src)
    _git("add", "-A", cwd=src)
    _git("commit", "-qm", "init", cwd=src)
    bare = tmp_path / "wfixture.git"
    _git("clone", "-q", "--bare", str(src), str(bare))
    home = tmp_path / "whome"
    home.mkdir()
    stubs = tmp_path / "stubs.ps1"
    stubs.write_text(PS_STUBS)
    env = {
        "HOME": str(home), "PATH": "/usr/bin:/bin", "USERPROFILE": str(home),
        "USERNAME": USER, "USERDOMAIN": "ZEDDOMAIN", "COMPUTERNAME": "ZEDTESTER-PC",
        "COURIER_SETUP_OS": "Windows_NT", "COURIER_REPO_URL": bare.as_uri(),
        "POWERSHELL_TELEMETRY_OPTOUT": "1",
    }
    return home, env, stubs


def run_ps(env, stubs, args=""):
    cmd = (f". '{stubs}'; Get-Content -Raw '{PS1}' | iex; "
           "Write-Output \"ALIVE rc=$LASTEXITCODE\"")
    return subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command", cmd],
                          env={**env, "COURIER_SETUP_ARGS": args}, capture_output=True, text=True, timeout=180)


@needs_pwsh
def test_ps1_check_mode_writes_nothing(win_env):
    home, env, stubs = win_env
    r = run_ps(env, stubs, "--check")
    assert "ALIVE rc=2" in r.stdout, r.stdout + r.stderr
    assert "WOULD_CLONE" in r.stdout
    assert not (home / "Courier").exists()
    assert not (home / "registered.txt").exists()
    assert not (home / "clip.txt").exists()


@needs_pwsh
def test_ps1_setup_registers_redacts_and_repeats(win_env):
    home, env, stubs = win_env
    r = run_ps(env, stubs)
    assert "ALIVE rc=" in r.stdout, r.stdout + r.stderr  # iex never closes the session
    report = (home / "Courier/setup-report.txt").read_text()
    clip = (home / "clip.txt").read_text()
    for text in (report, clip, r.stdout):
        assert USER not in text.lower() and "zedtester" not in text.lower()
        assert "ZEDDOMAIN" not in text and str(home) not in text
    assert "REGISTERED (logon task for this user; not started now)" in report
    assert "pagefile free 512 MB < 1024 MB" in report
    assert (home / "registered.txt").exists()
    r2 = run_ps(env, stubs)
    assert "[UP_TO_DATE]" in r2.stdout, r2.stdout
    assert "already present for this user" in r2.stdout


@needs_pwsh
def test_ps1_skips_admin_installer(win_env, tmp_path):
    home, env, stubs = win_env
    # Point at a fixture whose installer is the SYSTEM boot-task variant.
    src = tmp_path / "wsrc2"
    (src / "scripts/windows_worker").mkdir(parents=True)
    (src / "scripts/windows_worker/install_service.ps1").write_text(
        '$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest\n')
    _git("init", "-q", "-b", "integration/v1", cwd=src)
    _git("add", "-A", cwd=src)
    _git("commit", "-qm", "init", cwd=src)
    bare = tmp_path / "wfixture2.git"
    _git("clone", "-q", "--bare", str(src), str(bare))
    r = run_ps({**env, "COURIER_REPO_URL": bare.as_uri()}, stubs)
    assert "ALIVE rc=2" in r.stdout, r.stdout + r.stderr
    assert "installer in this checkout needs admin" in r.stdout
    assert not (home / "registered.txt").exists()
