"""Cross-Lane Asynchronous Event Bus Bridge with Topic Wildcards (P32)

Provides topic-based publish/subscribe messaging across lanes with AMQP-style
wildcards (* and #), backpressure buffer overflow management, subscriber error
isolation with Dead-Letter Queue (DLQ), and optional append-only journal persistence.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class OverflowPolicy(str, Enum):
    RAISE = "RAISE"
    DROP_OLDEST = "DROP_OLDEST"


class BufferOverflowError(Exception):
    """Raised when the event buffer exceeds max capacity and policy is RAISE."""
    pass


def match_topic_pattern(pattern: str, topic: str) -> bool:
    """Evaluate AMQP/MQTT-style topic pattern matching.

    '*' matches exactly one token separated by '.'.
    '#' matches zero or more tokens.
    """
    if pattern == "#" or pattern == topic:
        return True

    p_tokens = pattern.split(".")
    t_tokens = topic.split(".")

    def _match(p_idx: int, t_idx: int) -> bool:
        if p_idx == len(p_tokens) and t_idx == len(t_tokens):
            return True
        if p_idx == len(p_tokens):
            return False

        token = p_tokens[p_idx]
        if token == "#":
            if p_idx == len(p_tokens) - 1:
                return True
            for next_t in range(t_idx, len(t_tokens) + 1):
                if _match(p_idx + 1, next_t):
                    return True
            return False

        if t_idx == len(t_tokens):
            return False

        if token == "*" or token == t_tokens[t_idx]:
            return _match(p_idx + 1, t_idx + 1)

        return False

    return _match(0, 0)


@dataclass
class Event:
    event_id: str
    topic: str
    payload: Dict[str, Any]
    sender: str = "anonymous"
    timestamp: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "topic": self.topic,
            "payload": dict(self.payload),
            "sender": self.sender,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Event:
        return cls(
            event_id=str(data.get("event_id", "")),
            topic=str(data.get("topic", "")),
            payload=dict(data.get("payload", {})),
            sender=str(data.get("sender", "anonymous")),
            timestamp=data.get("timestamp"),
        )


@dataclass
class Subscriber:
    subscriber_id: str
    topic_pattern: str
    callback: Callable[[Event], None]


class EventBus:
    """Thread-safe, decoupled event bus with wildcard routing and resilience isolation."""

    def __init__(
        self,
        max_buffer_size: int = 1000,
        overflow_policy: OverflowPolicy = OverflowPolicy.DROP_OLDEST,
        journal_path: Optional[Path | str] = None,
    ) -> None:
        self.max_buffer_size = max_buffer_size
        self.overflow_policy = overflow_policy
        self.journal_path = Path(journal_path) if journal_path else None
        self._subscribers: List[Subscriber] = []
        self._recent_events: collections.deque[Event] = collections.deque()
        self._dlq: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

        if self.journal_path:
            self.journal_path.parent.mkdir(parents=True, exist_ok=True)

    def subscribe(
        self,
        topic_pattern: str,
        callback: Callable[[Event], None],
        subscriber_id: Optional[str] = None,
    ) -> str:
        with self._lock:
            sub_id = subscriber_id or f"sub_{uuid.uuid4().hex[:8]}"
            self._subscribers.append(
                Subscriber(
                    subscriber_id=sub_id,
                    topic_pattern=topic_pattern,
                    callback=callback,
                )
            )
            return sub_id

    def unsubscribe(self, subscriber_id: str) -> bool:
        with self._lock:
            initial_count = len(self._subscribers)
            self._subscribers = [s for s in self._subscribers if s.subscriber_id != subscriber_id]
            return len(self._subscribers) < initial_count

    def publish(self, event: Event) -> None:
        with self._lock:
            # Buffer & Backpressure management
            if len(self._recent_events) >= self.max_buffer_size:
                if self.overflow_policy == OverflowPolicy.RAISE:
                    raise BufferOverflowError(
                        f"EventBus buffer capacity exceeded ({self.max_buffer_size})"
                    )
                elif self.overflow_policy == OverflowPolicy.DROP_OLDEST:
                    self._recent_events.popleft()

            self._recent_events.append(event)

            # Persist to journal if configured
            if self.journal_path:
                with open(self.journal_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event.to_dict()) + "\n")

            # Match subscribers
            matched_subscribers = [
                s for s in self._subscribers if match_topic_pattern(s.topic_pattern, event.topic)
            ]

        # Dispatch outside the lock to prevent subscriber blocking
        for sub in matched_subscribers:
            try:
                sub.callback(event)
            except Exception as e:
                with self._lock:
                    self._dlq.append({
                        "event_id": event.event_id,
                        "subscriber_id": sub.subscriber_id,
                        "topic": event.topic,
                        "error": str(e),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

    def get_recent_events(self) -> List[Event]:
        with self._lock:
            return list(self._recent_events)

    def get_dlq(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._dlq)

    @classmethod
    def replay_journal(cls, journal_path: Path | str) -> List[Event]:
        path = Path(journal_path)
        if not path.exists():
            return []
        events: List[Event] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(Event.from_dict(json.loads(line)))
                    except Exception:
                        continue
        return events


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Event Bus CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pub_parser = subparsers.add_parser("publish", help="Publish an event to the bus journal")
    pub_parser.add_argument("--journal", required=True, help="Path to event journal JSONL file")
    pub_parser.add_argument("--topic", required=True, help="Topic path")
    pub_parser.add_argument("--payload", default="{}", help="JSON payload string")
    pub_parser.add_argument("--sender", default="cli-publisher", help="Sender identity")

    insp_parser = subparsers.add_parser("inspect", help="Inspect events from journal")
    insp_parser.add_argument("--journal", required=True, help="Path to event journal JSONL file")

    args = parser.parse_args(argv)

    if args.command == "publish":
        bus = EventBus(journal_path=args.journal)
        payload = json.loads(args.payload)
        ev = Event(
            event_id=f"ev_{int(time.time()*1000)}",
            topic=args.topic,
            payload=payload,
            sender=args.sender,
        )
        bus.publish(ev)
        print(json.dumps({
            "status": "PUBLISHED",
            "event_id": ev.event_id,
            "topic": ev.topic,
        }, indent=2))
        return 0

    elif args.command == "inspect":
        events = EventBus.replay_journal(args.journal)
        print(json.dumps({
            "total_events": len(events),
            "events": [e.to_dict() for e in events],
        }, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
