"""
Deliverable 2: Run-Verzeichnisstruktur
"""
import os
from pathlib import Path

class RunDirectoryDefiner:
    """
    Definiert die Standardstruktur für Courier-Runs.
    """
    def __init__(self, base_path: str = "runs"):
        # Relativ zum Project-Root oder absolut
        self.base_path = Path(base_path)

    def define_run_dir(self, run_id: str) -> Path:
        """
        Defines the path for a specific run ID.
        """
        return self.base_path / run_id

    def get_run_manifest_path(self, run_id: str) -> Path:
        """
        Path to the manifest of the run.
        """
        run_dir = self.define_run_dir(run_id)
        return run_dir / "run_manifest.json"
