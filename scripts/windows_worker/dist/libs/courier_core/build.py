"""Which controller build wrote a lifecycle.

CONTROLLER_STARTED carries build_identity(); because the controller is the
only writer, every event belongs to the build of the nearest preceding
CONTROLLER_STARTED (build_for_seq). This is attribution, not provenance:
nothing is trusted because of it.

- version:       courier_core.__version__
- build_id:      COURIER_BUILD_ID, set by the packaged launcher (lane L6);
                 null for a source checkout
- source_sha256: sha256 over the courier_core sources (null when the sources
                 are not readable, e.g. inside a frozen executable)
"""

from __future__ import annotations

import hashlib
import os
import platform
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import courier_core
from courier_core.events import Event, EventType

BUILD_ID_ENV = "COURIER_BUILD_ID"
MAX_BUILD_ID_LENGTH = 200


@lru_cache(maxsize=1)
def source_sha256() -> str | None:
    package = Path(courier_core.__file__).resolve().parent
    files = sorted(package.glob("*.py"))
    if not files:
        return None
    digest = hashlib.sha256()
    try:
        for path in files:
            digest.update(path.name.encode("utf-8") + b"\0")
            digest.update(path.read_bytes() + b"\0")
    except OSError:
        return None
    return digest.hexdigest()


def build_identity() -> dict:
    build_id = os.environ.get(BUILD_ID_ENV) or None
    return {"version": courier_core.__version__,
            "build_id": build_id[:MAX_BUILD_ID_LENGTH] if build_id else None,
            "source_sha256": source_sha256(),
            "python": platform.python_version()}


def build_for_seq(events: Iterable[Event], seq: int) -> dict | None:
    """The build recorded by the last CONTROLLER_STARTED at or before seq."""
    build = None
    for event in events:
        if event.seq is not None and event.seq > seq:
            break
        if event.type is EventType.CONTROLLER_STARTED:
            build = event.payload.get("build")
    return build
