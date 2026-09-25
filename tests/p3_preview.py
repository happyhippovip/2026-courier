"""Load server/app.py with the P3 cutover patch series applied, in a temp copy
only. The real server/app.py (P3, read-only) is never modified."""
import importlib.util
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "docs" / "p3" / "artifact-upload-cutover.patch"
# Cutover order: each patch applies on top of the previous one.
PATCHES = (PATCH, ROOT / "docs" / "p3" / "server-idempotency-cutover.patch")


def load_patched_server(tmp_path, monkeypatch):
    work = tmp_path / "p3"
    (work / "server").mkdir(parents=True)
    shutil.copy(ROOT / "server" / "app.py", work / "server" / "app.py")
    for patch in PATCHES:
        subprocess.run(["git", "apply", str(patch)], cwd=work, check=True, capture_output=True)
    monkeypatch.setenv("COURIER_API_KEY", "test-secret")
    monkeypatch.setenv("COURIER_VERIFIER_API_KEY", "verifier-secret")
    monkeypatch.setenv("COURIER_STATE_FILE", str(tmp_path / "central.json"))
    monkeypatch.setenv("COURIER_ARTIFACT_DIR", str(tmp_path / "artifact-store"))
    monkeypatch.setenv("COURIER_ARTIFACT_MAX_BYTES", "4096")
    spec = importlib.util.spec_from_file_location(f"server_app_p3_{tmp_path.name}", work / "server" / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WORKER = {"Authorization": "Bearer test-secret"}
VERIFIER = {"Authorization": "Bearer verifier-secret"}
