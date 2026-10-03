import json
import os
from typing import Dict, Any

class ProjectBasePrimitive:
    """MAC-10: Advance the safe-haven/project-continuation backend."""
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.state_file = os.path.join(project_root, ".courier_safe_haven.json")

    def init_safe_haven(self) -> None:
        if not os.path.exists(self.project_root):
            os.makedirs(self.project_root)
        if not os.path.exists(self.state_file):
            self.update_state({"version": 1, "active": True, "protected_paths": []})

    def update_state(self, state_data: Dict[str, Any]) -> None:
        with open(self.state_file, 'w') as f:
            json.dump(state_data, f)

    def read_state(self) -> Dict[str, Any]:
        if not os.path.exists(self.state_file):
            raise FileNotFoundError("Safe haven not initialized.")
        with open(self.state_file, 'r') as f:
            return json.load(f)
