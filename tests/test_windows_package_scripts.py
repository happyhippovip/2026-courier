"""The Windows package must contain the scripts uninstall actually calls."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "scripts" / "windows_worker" / "build_package.ps1"
UNINSTALL = ROOT / "scripts" / "windows_worker" / "uninstall.ps1"

REQUIRED = (
    "install.ps1",
    "install_service.ps1",
    "uninstall.ps1",
    "uninstall_user_data.ps1",
    "stop.ps1",
    "stop.bat",
    "status.ps1",
    "status.bat",
    "start.bat",
)


def test_package_refuses_to_omit_a_lifecycle_script():
    text = PACKAGE.read_text(encoding="utf-8")
    assert "Package is missing" in text
    assert "exit 1" in text
    for name in REQUIRED:
        assert f'"{name}"' in text


def test_shipped_dist_uninstall_matches_the_source_and_can_stop():
    root = ROOT / "scripts" / "windows_worker"
    for name in ("uninstall.ps1", "stop.ps1", "uninstall_user_data.ps1"):
        assert (root / name).read_bytes() == (root / "dist" / name).read_bytes()


def test_uninstall_helpers_are_in_the_package_list():
    uninstall = UNINSTALL.read_text(encoding="utf-8")
    package = PACKAGE.read_text(encoding="utf-8")
    for name in ("stop.ps1", "uninstall_user_data.ps1"):
        assert name in uninstall
        assert f'"{name}"' in package
