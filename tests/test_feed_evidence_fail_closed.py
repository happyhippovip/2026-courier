import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_local_evidence_injector_is_disabled_and_does_not_touch_ledger(tmp_path):
    ledger = tmp_path / "agent_handoff_ledger.json"
    original = b'{"sentinel":"must-not-change"}\n'
    ledger.write_bytes(original)

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "feed_evidence.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 2
    assert "local evidence injection is disabled" in result.stderr
    assert "Injected valid MACHINE_ARTIFACT" not in result.stdout
    assert ledger.read_bytes() == original
