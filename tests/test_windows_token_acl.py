"""The installer must not leave the controller token readable by every local user.

The scheduled task runs as SYSTEM, so SYSTEM and the installing user can
read the token. Inherited access for other users is removed.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLERS = (
    ROOT / "scripts" / "windows_worker" / "install.ps1",
    ROOT / "scripts" / "windows_worker" / "dist" / "install.ps1",
)


def test_token_acl_keeps_system_and_drops_inheritance():
    for path in INSTALLERS:
        text = path.read_text(encoding="utf-8")
        written = text.index("Set-Content $tokenPath")
        locked = text.index("icacls $tokenPath /inheritance:r")
        assert written < locked
        assert "*S-1-5-18:(R)" in text
        assert "could not restrict access" in text
