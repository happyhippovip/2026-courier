"""
Deliverable 3: State/Log/Artifact/Temp Isolation
"""
from pathlib import Path
from typing import Dict
from .run_structure import RunDirectoryDefiner

class RunIsolation:
    """
    State/Log/Artifact/Temp Isolation fertigstellen.
    """
    def __init__(self, run_definer: RunDirectoryDefiner, run_id: str):
        self.run_dir = run_definer.define_run_dir(run_id)
        
        # Isolation paths
        self.state_dir = self.run_dir / "state"
        self.log_dir = self.run_dir / "logs"
        self.artifact_dir = self.run_dir / "artifacts"
        self.temp_dir = self.run_dir / "temp"

    def ensure_isolation(self) -> Dict[str, str]:
        """
        Erstellt die isolierten Verzeichnisse.
        Keine physische RUN-Ausführung, aber die Struktur wird auf dem Dateisystem vorbereitet.
        """
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        return {
            "state": str(self.state_dir),
            "logs": str(self.log_dir),
            "artifacts": str(self.artifact_dir),
            "temp": str(self.temp_dir)
        }
