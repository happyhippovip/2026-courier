import requests
from typing import List, Optional
from scripts.coordination_ledger import CoordinationEvent
import os

class GitHubCoordinationAdapter:
    def __init__(self, repo: str, issue_number: int, token: Optional[str] = None):
        self.repo = repo
        self.issue_number = issue_number
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.base_url = f"https://api.github.com/repos/{self.repo}/issues/{self.issue_number}"
        
    def _headers(self):
        headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def read_events(self) -> List[CoordinationEvent]:
        # Reads all comments and extracts JSON codeblocks that match CoordinationEvent schema
        import json
        events = []
        response = requests.get(f"{self.base_url}/comments", headers=self._headers())
        if response.status_code != 200:
            return []
            
        for comment in response.json():
            body = comment.get("body", "")
            # Look for JSON block
            if "```json" in body:
                try:
                    parts = body.split("```json")
                    for part in parts[1:]:
                        json_str = part.split("```")[0].strip()
                        data = json.loads(json_str)
                        if "event_type" in data and "mission_id" in data:
                            events.append(CoordinationEvent.from_dict(data))
                except Exception:
                    continue
        return events

    def write_event(self, event: CoordinationEvent) -> bool:
        # Appends a new event as a comment
        import json
        body = f"Coordination Event:\\n```json\\n{json.dumps(event.to_dict(), indent=2)}\\n```"
        response = requests.post(
            f"{self.base_url}/comments",
            headers=self._headers(),
            json={"body": body}
        )
        return response.status_code == 201

