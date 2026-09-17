import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tests" / "boundaries" / "run_boundaries.py"
FINDINGS = ROOT / "tests" / "boundaries" / "findings"


def test_boundary_runner_is_bounded_and_does_not_write_evidence(tmp_path):
    findings_before = {path.name for path in FINDINGS.glob("*")}

    completed = subprocess.run(
        [sys.executable, str(RUNNER)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    # Exit 1 means the adversarial runner found a real boundary defect.  The
    # harness itself must still finish, emit a complete summary, and avoid
    # manufacturing durable proof files in the repository.
    assert completed.returncode in {0, 1}, completed.stderr
    assert "PROPERTIES_TESTED=14" in completed.stdout
    assert "AUTH_FAIL_CLOSED=YES" in completed.stdout
    assert "MALFORMED_INPUT_SAFE=YES" in completed.stdout
    assert not (tmp_path / "boundary_state.json").exists()
    assert {path.name for path in FINDINGS.glob("*")} == findings_before
