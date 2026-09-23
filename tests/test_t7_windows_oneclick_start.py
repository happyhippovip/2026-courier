"""T7: Kunden-Ein-Klick-Start (Windows) — Nachweis vor/nach der Aenderung.

Vor der Aenderung fehlen scripts/start_cannon_windows.ps1 und
start_cannon_windows.bat -> Existenz-Tests schlagen fehl (Problem belegt).
Nach der Aenderung muss alles gruen sein. Kein Netzwerk, kein Provider,
nur BEGRENZT (FINITE) local_fake-Modus. Kein fremder Prozess wird beendet.
"""
import subprocess
from pathlib import Path

from scripts.cannon_motor import CannonMotor

ROOT = Path(__file__).resolve().parents[1]
PS1 = ROOT / "scripts" / "start_cannon_windows.ps1"
BAT_SCRIPTS = ROOT / "scripts" / "start_cannon_windows.bat"
BAT_ROOT = ROOT / "start_cannon_windows.bat"


def test_start_scripts_exist():
    missing = [str(p) for p in (PS1, BAT_SCRIPTS, BAT_ROOT) if not p.is_file()]
    assert not missing, f"Ein-Klick-Start fehlt: {missing}"


def test_ps1_sets_bounded_local_fake():
    text = PS1.read_text(encoding="utf-8", errors="replace")
    for token in ("COURIER_STATE_DIR", "local_fake", "FINITE", "COURIER_LIMIT",
                  "LASTEXITCODE"):
        assert token in text, f"ps1 ohne {token}"
    # Negativ: kein Aufruf des echten Pfads (reine Erwaehnung in Kommentaren
    # zur Begruendung der local_fake-Garantie ist erlaubt und beabsichtigt).
    for bad in ("LiveMuseAdapter", "execute_canary", "muse exec"):
        assert bad not in text, f"ps1 zieht echten Muse-Pfad: {bad}"


def test_bat_sets_bounded_local_fake():
    for bat in (BAT_SCRIPTS, BAT_ROOT):
        text = bat.read_text(encoding="utf-8", errors="replace")
        for token in ("COURIER_STATE_DIR", "local_fake", "FINITE", "ERRORLEVEL"):
            assert token in text, f"{bat.name} ohne {token}"
        assert "exit /b" in text.lower(), f"{bat.name} ohne exit-Code"
        for bad in ("LiveMuseAdapter", "execute_canary", "muse exec"):
            assert bad not in text, f"{bat.name} mit echtem Muse-Pfad: {bad}"


def test_bounded_local_fake_run_completes(tmp_path):
    # Exakt die Parameter, die die Startskripte setzen: FINITE + Limit + local_fake.
    motor = CannonMotor(tmp_path)
    started = motor.start(mode="FINITE", limit=3, cooldown=0, local_fake=True)
    assert started.get("started") is True, started
    motor.run(max_steps=1000)
    inv = motor.invariants()
    assert inv["DONE_COUNT"] >= 1, inv
    assert inv["LOST_RESULTS"] == 0, inv
    assert inv["DUPLICATE_EXECUTIONS"] == 0, inv
    assert motor.state in ("COMPLETED", "IDLE"), motor.state


def test_cannon_page_untouched():
    out = subprocess.check_output(
        ["git", "-C", str(ROOT), "diff", "--name-only", "HEAD", "--",
         "app/cannon.html", "app/cannon.css", "app/cannon.js"], text=True)
    assert out.strip() == "", f"Cannon-Seite angefasst: {out!r}"
