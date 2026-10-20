"""Distributed Trace Context Propagator & W3C Traceparent Engine.

Compliant with W3C Trace Context specifications (traceparent, tracestate).
Provides carrier injection/extraction for HTTP and event buses, contextvar scope
management, child span inheritance, and fail-closed validation.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
import json
import os
import re
import secrets
import sys
from typing import Any, Iterator

_TRACE_ID_REGEX = re.compile(r"^[0-9a-f]{32}$")
_SPAN_ID_REGEX = re.compile(r"^[0-9a-f]{16}$")
_FLAGS_REGEX = re.compile(r"^[0-9a-f]{2}$")
_VERSION_REGEX = re.compile(r"^[0-9a-f]{2}$")

_INVALID_ALL_ZEROS_TRACE = "0" * 32
_INVALID_ALL_ZEROS_SPAN = "0" * 16

_CURRENT_TRACE: ContextVar[TraceContext | None] = ContextVar("current_trace_context", default=None)


class InvalidTraceContextError(ValueError):
    """Raised when a traceparent or tracestate header is malformed or invalid."""


@dataclass
class TraceContext:
    """Represents a distributed trace context (W3C Traceparent)."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    trace_flags: str = "01"
    version: str = "00"
    tracestate: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.trace_id = self.trace_id.lower()
        self.span_id = self.span_id.lower()
        if self.parent_span_id:
            self.parent_span_id = self.parent_span_id.lower()
        self.trace_flags = self.trace_flags.lower()
        self.version = self.version.lower()

    @classmethod
    def new_root(
        cls,
        sampled: bool = True,
        tracestate: dict[str, str] | None = None,
    ) -> TraceContext:
        """Create a new root trace context with randomly generated IDs."""
        trace_id = secrets.token_hex(16)
        span_id = secrets.token_hex(8)
        flags = "01" if sampled else "00"
        return cls(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=None,
            trace_flags=flags,
            version="00",
            tracestate=dict(tracestate) if tracestate else {},
        )

    def child_span(
        self,
        sampled: bool | None = None,
        tracestate: dict[str, str] | None = None,
    ) -> TraceContext:
        """Create a child span inheriting trace_id and parent span linkage."""
        child_span_id = secrets.token_hex(8)
        flags = self.trace_flags if sampled is None else ("01" if sampled else "00")
        state = dict(self.tracestate)
        if tracestate:
            state.update(tracestate)

        return TraceContext(
            trace_id=self.trace_id,
            span_id=child_span_id,
            parent_span_id=self.span_id,
            trace_flags=flags,
            version=self.version,
            tracestate=state,
        )

    def to_traceparent(self) -> str:
        """Serialize context to W3C traceparent header string."""
        return f"{self.version}-{self.trace_id}-{self.span_id}-{self.trace_flags}"

    def to_tracestate(self) -> str:
        """Serialize tracestate dictionary to comma-separated vendor string."""
        return ",".join(f"{k}={v}" for k, v in self.tracestate.items())

    @classmethod
    def from_traceparent(
        cls,
        header: str,
        tracestate_header: str | None = None,
        strict: bool = True,
    ) -> TraceContext:
        """Parse W3C traceparent and optional tracestate headers."""
        try:
            if not isinstance(header, str):
                raise InvalidTraceContextError("Header must be a string")

            parts = header.strip().split("-")
            if len(parts) != 4:
                raise InvalidTraceContextError(f"Traceparent must have 4 parts: {header}")

            version, trace_id, span_id, flags = parts

            if not _VERSION_REGEX.match(version) or version == "ff":
                raise InvalidTraceContextError(f"Invalid version: {version}")

            if not _TRACE_ID_REGEX.match(trace_id) or trace_id == _INVALID_ALL_ZEROS_TRACE:
                raise InvalidTraceContextError(f"Invalid trace-id: {trace_id}")

            if not _SPAN_ID_REGEX.match(span_id) or span_id == _INVALID_ALL_ZEROS_SPAN:
                raise InvalidTraceContextError(f"Invalid span-id: {span_id}")

            if not _FLAGS_REGEX.match(flags):
                raise InvalidTraceContextError(f"Invalid flags: {flags}")

            tracestate: dict[str, str] = {}
            if tracestate_header:
                for entry in tracestate_header.split(","):
                    entry = entry.strip()
                    if "=" in entry:
                        k, v = entry.split("=", 1)
                        tracestate[k.strip()] = v.strip()

            return cls(
                trace_id=trace_id,
                span_id=span_id,
                trace_flags=flags,
                version=version,
                tracestate=tracestate,
            )
        except Exception:
            if strict:
                raise
            return cls.new_root()

    def to_dict(self) -> dict[str, Any]:
        return {
            "traceparent": self.to_traceparent(),
            "tracestate": self.to_tracestate(),
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "trace_flags": self.trace_flags,
            "version": self.version,
            "tracestate_dict": self.tracestate,
        }


def current_trace_context() -> TraceContext | None:
    """Retrieve active trace context from thread-local contextvar."""
    return _CURRENT_TRACE.get()


@contextmanager
def trace_scope(context: TraceContext) -> Iterator[TraceContext]:
    """Scoped context manager for setting the active trace context."""
    token = _CURRENT_TRACE.set(context)
    try:
        yield context
    finally:
        _CURRENT_TRACE.reset(token)


def inject_http_headers(context: TraceContext, headers: dict[str, Any] | None = None) -> dict[str, str]:
    """Inject traceparent and tracestate into HTTP headers dictionary."""
    out = dict(headers) if headers else {}
    out["traceparent"] = context.to_traceparent()
    ts = context.to_tracestate()
    if ts:
        out["tracestate"] = ts
    return out


def extract_http_headers(headers: dict[str, Any], strict: bool = False) -> TraceContext | None:
    """Extract trace context from HTTP headers dictionary (case-insensitive)."""
    tp_key = next((k for k in headers if k.lower() == "traceparent"), None)
    if not tp_key or not headers[tp_key]:
        return None

    ts_key = next((k for k in headers if k.lower() == "tracestate"), None)
    ts_val = headers[ts_key] if ts_key else None

    return TraceContext.from_traceparent(str(headers[tp_key]), ts_val, strict=strict)


def inject_event(context: TraceContext, event: dict[str, Any]) -> dict[str, Any]:
    """Inject trace context metadata into event dictionary."""
    out = dict(event)
    out["_trace"] = {
        "traceparent": context.to_traceparent(),
        "tracestate": context.to_tracestate(),
        "trace_id": context.trace_id,
        "span_id": context.span_id,
    }
    return out


def extract_event(event: dict[str, Any], strict: bool = False) -> TraceContext | None:
    """Extract trace context from an event dictionary containing '_trace'."""
    trace_meta = event.get("_trace")
    if not isinstance(trace_meta, dict):
        return None

    tp = trace_meta.get("traceparent")
    if not tp:
        return None

    ts = trace_meta.get("tracestate")
    return TraceContext.from_traceparent(str(tp), ts, strict=strict)


def main() -> None:
    parser = argparse.ArgumentParser(description="Distributed Trace Context Engine (W3C)")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # generate
    gen_p = subparsers.add_parser("generate", help="Generate a new root trace context")
    gen_p.add_argument("--unsampled", action="store_true", help="Set unsampled flag")

    # parse
    parse_p = subparsers.add_parser("parse", help="Parse a traceparent header")
    parse_p.add_argument("--traceparent", required=True, help="Traceparent string")
    parse_p.add_argument("--tracestate", default=None, help="Tracestate string")

    # child
    child_p = subparsers.add_parser("child", help="Generate child span from parent")
    child_p.add_argument("--traceparent", required=True, help="Parent traceparent string")

    args = parser.parse_args()

    if args.action == "generate":
        ctx = TraceContext.new_root(sampled=not args.unsampled)
        print(f"traceparent: {ctx.to_traceparent()}")
        if ctx.tracestate:
            print(f"tracestate: {ctx.to_tracestate()}")
    elif args.action == "parse":
        ctx = TraceContext.from_traceparent(args.traceparent, args.tracestate, strict=True)
        print(json.dumps(ctx.to_dict(), indent=2))
    elif args.action == "child":
        parent = TraceContext.from_traceparent(args.traceparent, strict=True)
        child = parent.child_span()
        print(f"child traceparent: {child.to_traceparent()}")


if __name__ == "__main__":
    main()
