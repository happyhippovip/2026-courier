import json
import os
from pathlib import Path
from typing import List, Optional

import requests

from scripts.coordination_ledger import CoordinationEvent

EVENT_FENCE = "```json"
PAGE_SIZE = 100
MAX_PAGES = 50  # Bounded read: 5000 comments.


def extract_events_from_body(body: str) -> List[CoordinationEvent]:
    """Extract every valid CoordinationEvent JSON block from one comment body."""
    events: List[CoordinationEvent] = []
    if not isinstance(body, str) or EVENT_FENCE not in body:
        return events
    for part in body.split(EVENT_FENCE)[1:]:
        json_str = part.split("```")[0].strip()
        try:
            data = json.loads(json_str)
            if isinstance(data, dict) and "event_type" in data and "mission_id" in data:
                events.append(CoordinationEvent.from_dict(data))
        except (ValueError, TypeError):
            continue  # Malformed/foreign blocks never become state.
    return events


def render_event_body(event: CoordinationEvent) -> str:
    return f"Coordination Event:\n{EVENT_FENCE}\n{json.dumps(event.to_dict(), indent=2)}\n```"


class GitHubCoordinationAdapter:
    def __init__(self, repo: str, issue_number: int, token: Optional[str] = None, timeout: float = 30.0):
        self.repo = repo
        self.issue_number = issue_number
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.timeout = timeout
        self.base_url = f"https://api.github.com/repos/{self.repo}/issues/{self.issue_number}"

    def _headers(self):
        headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def read_events(self) -> List[CoordinationEvent]:
        """Read all coordination events from the issue, across every comment page.

        Raises RuntimeError on a failed page so callers never mistake a partial
        read for complete shared truth.
        """
        events: List[CoordinationEvent] = []
        for page in range(1, MAX_PAGES + 1):
            response = requests.get(
                f"{self.base_url}/comments",
                headers=self._headers(),
                params={"per_page": PAGE_SIZE, "page": page},
                timeout=self.timeout,
            )
            if response.status_code != 200:
                raise RuntimeError(f"Coordination ledger read failed: HTTP {response.status_code} (page {page})")
            comments = response.json()
            if not isinstance(comments, list):
                raise RuntimeError("Coordination ledger read failed: unexpected payload")
            for comment in comments:
                events.extend(extract_events_from_body(comment.get("body", "")))
            if len(comments) < PAGE_SIZE:
                return events
        raise RuntimeError("Coordination ledger read exceeded bounded page limit")

    def write_event(self, event: CoordinationEvent) -> bool:
        # Appends a new event as a comment
        response = requests.post(
            f"{self.base_url}/comments",
            headers=self._headers(),
            json={"body": render_event_body(event)},
            timeout=self.timeout,
        )
        return response.status_code == 201


class FileCoordinationStore:
    """Append-only JSONL mirror with the same read/write contract as the GitHub adapter.

    Used for offline operation and for fresh-process continuation proofs.
    """

    def __init__(self, path):
        self.path = Path(path)

    def read_events(self) -> List[CoordinationEvent]:
        if not self.path.exists():
            return []
        events: List[CoordinationEvent] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(CoordinationEvent.from_dict(json.loads(line)))
            except (ValueError, TypeError):
                continue  # A torn/foreign line never becomes state.
        return events

    def write_event(self, event: CoordinationEvent) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return True
