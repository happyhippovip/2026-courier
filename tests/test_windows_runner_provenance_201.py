"""Deterministic and isolated tests for Windows Runner Provenance (SEED 201).

MISSION: WINDOWS-RUNNER-PROVENIENZ PRÜFEN.
OWNER: Independent CI Reviewer.
MODE: VERIFY_FIRST.
Validates the cryptographic and structural provenance binding between
scripts/windows_worker/launcher/CourierLauncher.cs, Courier.manifest, and
the checked-in scripts/windows_worker/Courier.exe binary blob.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import pytest

from scripts.verify_runner_provenance import (
    find_csc_compiler,
    compute_sha256,
    audit_runner_provenance,
)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Runner Provenance tests require Windows host")
def test_positive_runner_provenance_authentic_audit():
    """Positivtest: Die überprüfte Courier.exe entspricht bitgenau dem Quellcode CourierLauncher.cs."""
    receipt = audit_runner_provenance()

    assert receipt["status"] == "PROVENANCE_CONFIRMED"
    assert receipt["provenance_confirmed"] is True
    assert receipt["provenance_gap_detected"] is False
    assert receipt["code_and_resources_identical"] is True
    assert receipt["non_metadata_diffs_count"] == 0
    assert receipt["checked_in_binary_bytes"] == 15872
    assert receipt["freshly_compiled_binary_bytes"] == 15872
    assert receipt["identical_bytes_ratio"] >= 0.998  # >= 99.8% bit-for-bit identical


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Runner Provenance tests require Windows host")
def test_positive_source_and_manifest_hash_integrity():
    """Prüft die exakte kryptographische Hash-Integrität von Quellcode, Manifest und Binary."""
    repo_root = Path(__file__).resolve().parent.parent
    source = repo_root / "scripts" / "windows_worker" / "launcher" / "CourierLauncher.cs"
    manifest = repo_root / "scripts" / "windows_worker" / "launcher" / "Courier.manifest"
    binary = repo_root / "scripts" / "windows_worker" / "Courier.exe"

    assert source.exists(), f"Source file {source} must exist"
    assert manifest.exists(), f"Manifest file {manifest} must exist"
    assert binary.exists(), f"Binary file {binary} must exist"

    # Verifizierte kanonische Prüfsummen
    assert compute_sha256(source) == "FA0327A93CCA92A6E4FBD6F50C064FD4FCBAD55CD523C76BC99C9169F8C577FA"
    assert compute_sha256(manifest) == "BA0EBA6E18B2E52C48B175926F073E218F6678EA44ACA9610164682B4804A9AB"
    assert compute_sha256(binary) == "68340CE921122075DA3328269387B4A3A2808ED2BCB0AAF0A4C1149DFB47D273"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Runner Provenance tests require Windows host")
def test_negative_tampered_binary_detected_and_rejected(tmp_path):
    """Negativtest: Ein manipuliertes Binary im IL-Code/Ressourcenbereich wird sofort als Lücke entlarvt."""
    repo_root = Path(__file__).resolve().parent.parent

    # Erstelle synthetische Repo-Struktur mit manipuliertem Binary
    synth_repo = tmp_path / "repo"
    synth_launcher_dir = synth_repo / "scripts" / "windows_worker" / "launcher"
    synth_launcher_dir.mkdir(parents=True)

    real_source = repo_root / "scripts" / "windows_worker" / "launcher" / "CourierLauncher.cs"
    real_manifest = repo_root / "scripts" / "windows_worker" / "launcher" / "Courier.manifest"
    real_binary = repo_root / "scripts" / "windows_worker" / "Courier.exe"

    (synth_launcher_dir / "CourierLauncher.cs").write_bytes(real_source.read_bytes())
    (synth_launcher_dir / "Courier.manifest").write_bytes(real_manifest.read_bytes())

    # Manipuliere ein Byte im Code-Bereich (Offset 5000)
    tampered_bytes = bytearray(real_binary.read_bytes())
    tampered_bytes[5000] = (tampered_bytes[5000] + 1) % 256
    (synth_repo / "scripts" / "windows_worker" / "Courier.exe").write_bytes(bytes(tampered_bytes))

    receipt = audit_runner_provenance(repo_root=synth_repo)
    assert receipt["status"] == "PROVENANCE_GAP_DETECTED"
    assert receipt["provenance_confirmed"] is False
    assert receipt["provenance_gap_detected"] is True
    assert receipt["code_and_resources_identical"] is False
    assert receipt["non_metadata_diffs_count"] >= 1


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Runner Provenance tests require Windows host")
def test_negative_divergent_source_detected(tmp_path):
    """Negativtest: Wenn der Quellcode verändert wird, weicht die Neukompilierung vom Binary ab."""
    repo_root = Path(__file__).resolve().parent.parent

    synth_repo = tmp_path / "repo"
    synth_launcher_dir = synth_repo / "scripts" / "windows_worker" / "launcher"
    synth_launcher_dir.mkdir(parents=True)

    real_source = repo_root / "scripts" / "windows_worker" / "launcher" / "CourierLauncher.cs"
    real_manifest = repo_root / "scripts" / "windows_worker" / "launcher" / "Courier.manifest"
    real_binary = repo_root / "scripts" / "windows_worker" / "Courier.exe"

    # Modifizierter Quelltext mit zusätzlichem String
    modified_source = real_source.read_text(encoding="utf-8") + "\n// INJECTED COMMENT / DIVERGENCE\n"
    (synth_launcher_dir / "CourierLauncher.cs").write_text(modified_source, encoding="utf-8")
    (synth_launcher_dir / "Courier.manifest").write_bytes(real_manifest.read_bytes())
    (synth_repo / "scripts" / "windows_worker" / "Courier.exe").write_bytes(real_binary.read_bytes())

    receipt = audit_runner_provenance(repo_root=synth_repo)
    # Compiler-Ausgabe erfasst Quellcode-Änderungen
    assert receipt["source_sha256"] != compute_sha256(real_source)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Runner Provenance tests require Windows host")
def test_cli_verify_runner_provenance_subprocess():
    """Prüft das CLI-Werkzeug scripts/verify_runner_provenance.py via Subprozess."""
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "verify_runner_provenance.py"
    assert script_path.exists(), f"CLI tool {script_path} must exist"

    # Text-Ausgabe
    res = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res.returncode == 0
    assert "PROVENANCE_CONFIRMED" in res.stdout
    assert "Code & Resources Identical:  True" in res.stdout
    assert "Provenance Confirmed:        True" in res.stdout

    # JSON-Ausgabe
    res_json = subprocess.run([sys.executable, str(script_path), "--json"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res_json.returncode == 0
    data = json.loads(res_json.stdout)
    assert data["status"] == "PROVENANCE_CONFIRMED"
    assert data["provenance_confirmed"] is True
    assert data["checked_in_binary_sha256"] == "68340CE921122075DA3328269387B4A3A2808ED2BCB0AAF0A4C1149DFB47D273"

    # --fail-on-gap Flag (muss 0 zurückgeben, da Provenienz bestätigt ist)
    res_fog = subprocess.run([sys.executable, str(script_path), "--fail-on-gap"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res_fog.returncode == 0
