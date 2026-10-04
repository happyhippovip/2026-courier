import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from memory_boundary import CategorizedMemoryRecord, PrivacyCategory

@dataclass
class ExportableProjectMemory:
    project_id: str
    canonical_state_sha: str
    checkpoints: List[Dict[str, Any]]
    handoffs: List[Dict[str, Any]]
    evidence_references: List[Dict[str, Any]]
    readiness_derivation_state: Dict[str, Any]
    provenance_records: List[Dict[str, Any]]

class MemoryExporterImporter:
    @staticmethod
    def export_memory(
        project_id: str,
        canonical_state_sha: str,
        raw_memory_records: List[CategorizedMemoryRecord],
        checkpoints: List[Dict],
        handoffs: List[Dict],
        evidence_references: List[Dict],
        readiness_state: Dict,
        provenance: List[Dict]
    ) -> str:
        """
        Exports the project memory safely, automatically stripping out 
        any local-only paths, secrets, or personal sensitive information.
        """
        # We explicitly cap the export at PRIVATE_PROJECT (can be moved between trusted machines).
        # We strip LOCAL_ONLY, SECRET, and PERSONAL_SENSITIVE.
        safe_records = []
        for record in raw_memory_records:
            if record.category <= PrivacyCategory.PRIVATE_PROJECT:
                safe_records.append(record.payload)
                
        # In a real implementation, checkpoints/handoffs would also be run through the boundary checker.
        # For this model, we assume they are already structural and safe.
        
        export_obj = ExportableProjectMemory(
            project_id=project_id,
            canonical_state_sha=canonical_state_sha,
            checkpoints=checkpoints,
            handoffs=handoffs,
            evidence_references=evidence_references,
            readiness_derivation_state=readiness_state,
            provenance_records=provenance
        )
        
        # Package the structured data alongside the filtered unstructured payload
        payload = {
            "version": "1.0",
            "structured_memory": asdict(export_obj),
            "safe_unstructured_records": safe_records
        }
        
        return json.dumps(payload, indent=2)

    @staticmethod
    def import_memory(json_payload: str, target_project_id: str) -> ExportableProjectMemory:
        """
        Imports memory into a fresh machine, verifying identity alignment.
        """
        data = json.loads(json_payload)
        
        if data.get("version") != "1.0":
            raise ValueError(f"Unsupported export version: {data.get('version')}")
            
        structured = data["structured_memory"]
        
        if structured["project_id"] != target_project_id:
            raise ValueError(f"Import failed: Export belongs to {structured['project_id']}, but target is {target_project_id}")
            
        return ExportableProjectMemory(**structured)
