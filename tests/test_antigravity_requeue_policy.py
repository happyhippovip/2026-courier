"""The Antigravity away-queue procedure must not resend a finished prompt."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs" / "v1" / "orchestration" / "AWAY_QUEUE_REFILL_PROTOCOL.md"
INSTALLER = ROOT / "scripts" / "windows_worker" / "install_service.ps1"


def test_completed_fingerprint_is_not_requeued():
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "65x or 100x" not in text
    assert "e.g. 65 or 100" not in text
    assert "Queue this token once." in text
    assert "fingerprint is already completed" in text
    assert "A completed workkey does not send the same prompt again." in text
    assert "do not queue it again while that copy is pending" in text
    assert "scripts/continuation_gate.py" in text
    assert "Unknown or missing cost is rejected and is not stored as 0." in text


def test_one_new_unit_can_still_be_queued():
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "Do exactly ONE NEW useful unit." in text
    assert "queue the NEXT SELF-REFILLING UNIT token once" in text
    assert "/loop 5m /courier-night-loop" in text


def test_human_gates_stay_single_decisions():
    text = PROTOCOL.read_text(encoding="utf-8")
    for gate in (
        "new spend",
        "secrets and login",
        "irreversible account changes",
        "unauthorized merge",
        "security-critical change",
        "legally relevant publication",
    ):
        assert gate in text
    assert "No approval is invented." in text
    assert "repeated 1/2/3 menu" in text


def test_windows_worker_schedule_still_starts_the_product():
    text = INSTALLER.read_text(encoding="utf-8")
    assert "Register-ScheduledTask" in text
    assert 'Join-Path $InstallDir "Courier.exe"' in text
    assert "prompt" not in text.lower()
