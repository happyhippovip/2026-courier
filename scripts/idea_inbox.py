import json
import os
import uuid
import datetime
from typing import Dict, Any, Optional

class IdeaInbox:
    def __init__(self, db_path: str = ".courier_state/idea_inbox.json"):
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if not os.path.exists(self.db_path):
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _read_all(self) -> list:
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_all(self, data: list):
        # Atomic write
        temp_path = self.db_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_path, self.db_path)

    def add_idea(self, raw_text: str, source: str = "human",
                 priority: str = "normal", risk: str = "unknown",
                 effort: str = "unknown", reversibility: str = "unknown") -> Dict[str, Any]:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        idea = {
            "idea_id": str(uuid.uuid4()),
            "raw_text": raw_text,
            "normalized_intent": None,
            "goal_id": None,
            "source": source,
            "priority": priority,
            "risk": risk,
            "effort": effort,
            "reversibility": reversibility,
            "status": "NEW",
            "created_at": now,
            "updated_at": now
        }
        data = self._read_all()
        data.append(idea)
        self._write_all(data)
        return idea

    def update_idea(self, idea_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data = self._read_all()
        for i, idea in enumerate(data):
            if idea["idea_id"] == idea_id:
                idea.update(updates)
                idea["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self._write_all(data)
                return idea
        return None

    def get_pending_ideas(self) -> list:
        return [idea for idea in self._read_all() if idea["status"] == "NEW"]
