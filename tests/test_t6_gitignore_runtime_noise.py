"""T6: Motor-Laufzeitdateien duerfen kein Git-Rauschen erzeugen.

Beleg-Test: ein kurzer local_fake-Lauf (BEGRENZT, limit=1) mit state_dir
INNERHALB der Arbeitskopie erzeugt motor.json, queue.json,
results/*.result.json und supervisor.lock. Ohne .gitignore-Eintraege
meldet `git status` sie als untracked (`??`) - das ist das Rauschen.
Zusaetzlich wird ein Absturz-Rest simuliert (`*.tmp`): der Executor und
die Queue schreiben atomar ueber `<name>.tmp`
(scripts/cannon_motor.py: deterministic_executor/motor._save;
scripts/work_queue.py: save), ein harter Absturz dazwischen laesst die
.tmp-Datei liegen.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.mac_adapter import MacAdapter  # noqa: E402

PROBE = ROOT / "t6-gitignore-probe-state"


def _git_check_ignored(relpath):
    """True, wenn relpath per .gitignore ignoriert wird."""
    proc = subprocess.run(
        ["git", "check-ignore", "--", relpath],
        cwd=str(ROOT), capture_output=True, text=True)
    return proc.returncode == 0


def test_local_fake_runtime_state_is_gitignored():
    if PROBE.exists():
        shutil.rmtree(PROBE)
    try:
        adapter = MacAdapter(PROBE)
        adapter.dauerlauf(art="begrenzt", limit=1, cooldown=0.0,
                          max_cycles=20, idle_sleep=0.0, local_fake=True)
        assert (PROBE / "motor.json").exists(), "probe lief nicht (motor.json fehlt)"
        assert (PROBE / "queue.json").exists(), "probe lief nicht (queue.json fehlt)"
        assert list((PROBE / "results").glob("*.result.json")), \
            "probe lief nicht (kein *.result.json)"
        assert (PROBE / "supervisor.lock").exists(), \
            "probe lief nicht (supervisor.lock fehlt)"
        # Simulierter Absturz-Rest eines atomaren .tmp-Schreibzugriffs.
        (PROBE / "results" / "probe-crash.result.tmp").write_text(
            "{}\n", encoding="utf-8")

        files = sorted(p for p in PROBE.rglob("*") if p.is_file())
        assert files, "probe erzeugte keine Dateien"
        noisy = [str(p.relative_to(ROOT)) for p in files
                 if not _git_check_ignored(str(p.relative_to(ROOT)))]
        assert not noisy, (
            "laufzeit-dateien erzeugen git-rauschen (untracked):\n"
            + "\n".join("?? " + name for name in noisy))
    finally:
        shutil.rmtree(PROBE, ignore_errors=True)
