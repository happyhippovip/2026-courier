import json
import os
from typing import Dict, Any

class CheckpointStore:
    """MAC-03: Persist resumable verified checkpoints."""
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        if not os.path.exists(storage_path):
            os.makedirs(storage_path)

    def save_checkpoint(self, checkpoint_id: str, data: Dict[str, Any]) -> str:
        filepath = os.path.join(self.storage_path, f"{checkpoint_id}.json")
        with open(filepath, 'w') as f:
            json.dump(data, f)
        return filepath

    def load_checkpoint(self, checkpoint_id: str) -> Dict[str, Any]:
        filepath = os.path.join(self.storage_path, f"{checkpoint_id}.json")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Checkpoint {checkpoint_id} not found.")
        with open(filepath, 'r') as f:
            return json.load(f)
