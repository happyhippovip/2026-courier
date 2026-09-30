"""Courier desktop overlay package (visualization only, never controls agents)."""

from .event_bus import (
    EVENT_TYPES,
    MAX_SUMMARY_LEN,
    EventBusError,
    emit,
    read_events,
    replay,
    validate_event,
)

__all__ = [
    "EVENT_TYPES",
    "MAX_SUMMARY_LEN",
    "EventBusError",
    "emit",
    "read_events",
    "replay",
    "validate_event",
]
