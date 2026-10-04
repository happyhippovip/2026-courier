import sys
import json
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from memory_export_import import MemoryExporterImporter, ExportableProjectMemory
from memory_boundary import CategorizedMemoryRecord, PrivacyCategory

def test_windows_to_fresh_windows_export_import_roundtrip():
    # 1. Setup simulated Windows source memory
    raw_records = [
        CategorizedMemoryRecord("r1", PrivacyCategory.PUBLIC_PROJECT, "Compiler: MSVC"),
        CategorizedMemoryRecord("r2", PrivacyCategory.PRIVATE_PROJECT, "Internal roadmap"),
        CategorizedMemoryRecord("r3", PrivacyCategory.LOCAL_ONLY, "C:/Users/winuser/AppData/Local/Temp"), # Should be stripped
        CategorizedMemoryRecord("r4", PrivacyCategory.SECRET, "github_pat_111111"), # Should be stripped
    ]
    
    checkpoints = [{"id": "chk-1", "status": "landed"}]
    handoffs = [{"id": "ho-1", "active_writer": "win-agent-1"}]
    evidence = [{"id": "ev-1", "type": "build_success"}]
    readiness = {"installer": "READY"}
    provenance = [{"claim": "ev-1", "source": "pytest"}]
    
    # 2. Perform Export (Windows Source)
    export_json = MemoryExporterImporter.export_memory(
        project_id="PROJ-WIN-2026",
        canonical_state_sha="abc123sha",
        raw_memory_records=raw_records,
        checkpoints=checkpoints,
        handoffs=handoffs,
        evidence_references=evidence,
        readiness_state=readiness,
        provenance=provenance
    )
    
    # Verify the boundary filter worked on export
    parsed_export = json.loads(export_json)
    safe_unstructured = parsed_export["safe_unstructured_records"]
    assert "Compiler: MSVC" in safe_unstructured
    assert "Internal roadmap" in safe_unstructured
    assert "C:/Users/winuser/AppData/Local/Temp" not in safe_unstructured
    assert "github_pat_111111" not in safe_unstructured
    
    # 3. Perform Import (Fresh Windows Destination)
    imported_mem = MemoryExporterImporter.import_memory(export_json, target_project_id="PROJ-WIN-2026")
    
    # Verify structural integrity
    assert imported_mem.project_id == "PROJ-WIN-2026"
    assert imported_mem.canonical_state_sha == "abc123sha"
    assert imported_mem.checkpoints[0]["status"] == "landed"
    assert imported_mem.readiness_derivation_state["installer"] == "READY"
    assert imported_mem.provenance_records[0]["source"] == "pytest"

def test_import_fails_on_project_id_mismatch():
    export_json = MemoryExporterImporter.export_memory(
        project_id="PROJ-A",
        canonical_state_sha="sha",
        raw_memory_records=[], checkpoints=[], handoffs=[], evidence_references=[], readiness_state={}, provenance=[]
    )
    
    # Try to import PROJ-A export into PROJ-B
    with pytest.raises(ValueError, match="target is PROJ-B"):
        MemoryExporterImporter.import_memory(export_json, target_project_id="PROJ-B")
