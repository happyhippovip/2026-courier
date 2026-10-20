"""Install must not continue after a failed task unregister or register.

Static contract only. This does not run PowerShell and does not build an EXE.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    ROOT / "scripts" / "windows_worker" / "install.ps1",
    ROOT / "scripts" / "windows_worker" / "dist" / "install.ps1",
    ROOT / "scripts" / "windows_worker" / "install_service.ps1",
)


def test_failed_unregister_or_register_stops_the_install():
    for path in SCRIPTS:
        text = path.read_text(encoding="utf-8")
        unregister = text.index("Unregister-ScheduledTask")
        still = text.index("the scheduled task is still present")
        register = text.index("Register-ScheduledTask")
        missing = text.index("the scheduled task was not registered")
        assert unregister < still < register < missing, path.name
        assert "exit 1" in text[still:register], path.name
        assert "exit 1" in text[missing:missing + 400], path.name
