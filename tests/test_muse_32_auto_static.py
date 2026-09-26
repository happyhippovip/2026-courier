"""Static guards for the Muse Auto trio (no shell required).

Pins the safe STRUCTURE of the new starters; live proof (real muse,
desktop shortcuts, staged runs) needs a working shell runner and is
tracked separately. Assertions:

- probe_muse.ps1: verifies Get-Command muse + `muse --help` on-machine,
  detects --yolo from REAL help text only, writes runtime/muse_probe.json,
  has a timeout, never launches a session, no Invoke-Expression.
- launch_32_auto.ps1: trio targets 16/32/64 (default 32), reuses the
  existing probe + supervisor + wt launcher (no duplicated wt logic),
  chain gate incl. 64-needs-32-PASS, per-stage proof files, slow poll
  only, YOLO fail-closed, never monitor/READY-only mode.
- install_desktop_shortcuts.ps1: writes exactly the trio (+ conditional
  YOLO), never touches Muse Original, no destructive/system changes.
- stop_all_slots.ps1: per-slot exact supervisor stop loop, no broad kills.
- all new scripts: no P3/Google contact, no taskkill/Stop-Process.
"""
from pathlib import Path

WALL_DIR = Path(__file__).resolve().parent.parent / "scripts" / "windows_muse_wall"

BANNED_KILL = ("taskkill", "Stop-Process", "pkill", "killall")
BANNED_P3 = ("server/app.py", "server\\app.py", "run_waitress", "launch_server_hidden")
BANNED_EXEC = ("Invoke-Expression",)


def read(name):
    path = WALL_DIR / name
    assert path.is_file(), name
    return path.read_text(encoding="utf-8")


def test_probe_verifies_muse_on_machine():
    text = read("probe_muse.ps1")
    assert "Get-Command muse" in text
    assert "muse --help" in text or "--help" in text
    assert "runtime\\muse_probe.json" in text or "runtime/muse_probe.json" in text


def test_probe_detects_yolo_from_real_help_only():
    text = read("probe_muse.ps1")
    assert "--yolo" in text
    assert "yolo_supported" in text
    # The probe must never START a session: exactly one muse invocation,
    # and it is `muse --help` (yolo appears only as a help-text regex).
    assert text.count("& $exe") == 1
    assert "& $exe --help" in text


def test_probe_has_timeout_and_is_fail_closed():
    text = read("probe_muse.ps1")
    assert "TimeoutSeconds" in text
    assert text.count("throw") >= 2


def test_auto_has_trio_targets_with_32_default():
    text = read("launch_32_auto.ps1")
    assert "ValidateSet(16, 32, 64)" in text
    assert "[int]$Target = 32" in text
    assert "ValidateSet(1, 4, 8, 16, 32, 64)" in text


def test_auto_reuses_existing_probe_supervisor_launcher():
    text = read("launch_32_auto.ps1")
    assert "probe_muse.ps1" in text
    assert "muse_wall_launcher.ps1" in text
    assert "-SlotCommand $slotCommand" in text
    assert "supervisor init" in text
    assert "supervisor admit" in text
    # No duplicated Windows Terminal logic in the auto starter.
    assert "wt.exe" not in text
    assert "new-tab" not in text
    assert "split-pane" not in text


def test_auto_never_runs_monitor_mode():
    text = read("launch_32_auto.ps1")
    assert "$slotCommand = 'muse'" in text
    assert "watcher.py" not in text


def test_auto_chain_gate_requires_previous_pass():
    text = read("launch_32_auto.ps1")
    assert "GATE_BLOCKED" in text
    assert "@(1, 4, 8, 16, 32, 64)" in text
    assert "TARGET_GATE" in text


def test_auto_writes_per_stage_proof():
    text = read("launch_32_auto.ps1")
    assert "stage-{0:D2}.json" in text
    assert "runtime\\proof" in text


def test_auto_yolo_is_fail_closed():
    text = read("launch_32_auto.ps1")
    assert "probe.yolo_supported" in text
    assert "YOLO refused" in text
    assert "$slotCommand = 'muse --yolo'" in text


def test_auto_polls_slowly_no_busy_loop():
    text = read("launch_32_auto.ps1")
    assert "Start-Sleep -Seconds 2" in text
    assert "while ($true)" not in text


def test_installer_writes_exactly_the_trio():
    text = read("install_desktop_shortcuts.ps1")
    assert "Muse 16 Auto" in text
    assert "Muse 32 Auto" in text
    assert "Muse 64 Auto" in text
    assert "-Target 16" in text
    assert "-Target 32" in text
    assert "-Target 64" in text


def test_installer_yolo_is_conditional_on_probe():
    text = read("install_desktop_shortcuts.ps1")
    assert "Muse 32 YOLO" in text
    assert "yoloSupported" in text
    assert "MUSE_32_YOLO_SHORTCUT=SKIPPED" in text


def test_installer_never_touches_muse_original():
    text = read("install_desktop_shortcuts.ps1")
    assert "Muse Original" in text
    assert "MUSE_ORIGINAL_PRESERVED" in text
    assert "Remove-Item" not in text
    assert "Move-Item" not in text


def test_stop_all_uses_exact_per_slot_stop():
    text = read("stop_all_slots.ps1")
    assert "supervisor stop" in text
    assert "--slot $slot" in text


def test_new_scripts_have_no_broad_kills():
    for name in (
        "probe_muse.ps1",
        "launch_32_auto.ps1",
        "install_desktop_shortcuts.ps1",
        "stop_all_slots.ps1",
    ):
        text = read(name)
        lowered = text.lower()
        for banned in BANNED_KILL:
            assert banned.lower() not in lowered, (name, banned)
        for banned in BANNED_EXEC:
            assert banned not in text, (name, banned)


def test_new_scripts_do_not_touch_p3_or_google():
    for name in (
        "probe_muse.ps1",
        "launch_32_auto.ps1",
        "install_desktop_shortcuts.ps1",
        "stop_all_slots.ps1",
    ):
        text = read(name)
        for banned in BANNED_P3:
            assert banned not in text, (name, banned)
        lowered = text.lower()
        # The only allowed mention is the explicit no-contact contract line.
        stripped = lowered.replace("no google/antigravity/p3 contact", "")
        assert "antigravity" not in stripped, name
        assert "run_antigravity" not in stripped, name
        assert "google" not in stripped, name
