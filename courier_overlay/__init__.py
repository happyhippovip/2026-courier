"""Courier desktop overlay package (visualization only, never controls agents)."""

from .event_bus import (
    EVENT_TYPES,
    MAX_SUMMARY_LEN,
    EventBusError,
    emit,
    read_events,
    replay,
    scan_report,
    validate_event,
)
from .replay_harness import (
    CANONICAL_SEQUENCES,
    LIFECYCLE_BLOCKED,
    LIFECYCLE_CUSTOMS_REJECTED,
    LIFECYCLE_MULTI_AGENT,
    LIFECYCLE_SUCCESS,
    ReplayEvent,
    ReplayHarness,
    run_canary_acceptance,
)

__all__ = [
    "CANONICAL_SEQUENCES",
    "EVENT_TYPES",
    "EventBusError",
    "LIFECYCLE_BLOCKED",
    "LIFECYCLE_CUSTOMS_REJECTED",
    "LIFECYCLE_MULTI_AGENT",
    "LIFECYCLE_SUCCESS",
    "MAX_SUMMARY_LEN",
    "ReplayEvent",
    "ReplayHarness",
    "emit",
    "read_events",
    "replay",
    "run_canary_acceptance",
    "scan_report",
    "validate_event",
]
