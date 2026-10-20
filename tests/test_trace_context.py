"""Tests for courier_core.trace_context - W3C Trace Context Propagator."""

from __future__ import annotations

import json
import pytest

from courier_core.trace_context import (
    TraceContext,
    InvalidTraceContextError,
    current_trace_context,
    trace_scope,
    inject_http_headers,
    extract_http_headers,
    inject_event,
    extract_event,
)


def test_w3c_traceparent_generation_and_parsing():
    ctx = TraceContext.new_root(sampled=True)

    assert len(ctx.trace_id) == 32
    assert len(ctx.span_id) == 16
    assert ctx.trace_flags == "01"
    assert ctx.parent_span_id is None

    header = ctx.to_traceparent()
    parts = header.split("-")
    assert len(parts) == 4
    assert parts[0] == "00"
    assert parts[1] == ctx.trace_id
    assert parts[2] == ctx.span_id
    assert parts[3] == "01"

    # Parse back
    parsed = TraceContext.from_traceparent(header)
    assert parsed.trace_id == ctx.trace_id
    assert parsed.span_id == ctx.span_id
    assert parsed.trace_flags == "01"


def test_child_span_correlation_and_inheritance():
    parent = TraceContext.new_root(sampled=True, tracestate={"tenant": "courier-L3"})
    child = parent.child_span()

    # Invariants
    assert child.trace_id == parent.trace_id
    assert child.parent_span_id == parent.span_id
    assert child.span_id != parent.span_id
    assert len(child.span_id) == 16
    assert child.trace_flags == parent.trace_flags
    assert child.tracestate == parent.tracestate


def test_fail_closed_validation_and_tamper_defense():
    invalid_headers = [
        "00-00000000000000000000000000000000-00f067aa0ba902b7-01",  # all zero trace-id
        "00-4bf92f3577b34da6a3ce929d0e0e4736-0000000000000000-01",  # all zero span-id
        "ff-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",  # invalid version ff
        "00-4bf92f3577b34da6a3ce929d0e0e473Z-00f067aa0ba902b7-01",  # non-hex char Z
        "00-short-00f067aa0ba902b7-01",                              # short trace-id
        "invalid-header-string",
    ]

    for bad in invalid_headers:
        with pytest.raises(InvalidTraceContextError):
            TraceContext.from_traceparent(bad, strict=True)

    # In non-strict mode, invalid header gracefully falls back to generating a valid new root
    fallback = TraceContext.from_traceparent("corrupt-header", strict=False)
    assert fallback is not None
    assert len(fallback.trace_id) == 32


def test_tracestate_handling():
    ctx = TraceContext.new_root(tracestate={"vendor1": "val1", "vendor2": "val2"})
    header = ctx.to_tracestate()
    assert "vendor1=val1" in header
    assert "vendor2=val2" in header

    parsed = TraceContext.from_traceparent(
        ctx.to_traceparent(),
        tracestate_header="vendor1=val1,vendor2=val2",
    )
    assert parsed.tracestate == {"vendor1": "val1", "vendor2": "val2"}


def test_carrier_injection_and_extraction():
    ctx = TraceContext.new_root(sampled=True, tracestate={"courier": "worker-1"})

    # HTTP Carrier
    headers = {"Content-Type": "application/json"}
    injected_headers = inject_http_headers(ctx, headers)
    assert "traceparent" in injected_headers
    assert "tracestate" in injected_headers

    extracted_http = extract_http_headers(injected_headers)
    assert extracted_http is not None
    assert extracted_http.trace_id == ctx.trace_id
    assert extracted_http.span_id == ctx.span_id
    assert extracted_http.tracestate == {"courier": "worker-1"}

    # Case-insensitive header lookup
    upper_headers = {"TRACEPARENT": ctx.to_traceparent()}
    extracted_upper = extract_http_headers(upper_headers)
    assert extracted_upper is not None
    assert extracted_upper.trace_id == ctx.trace_id

    # Event Carrier
    event = {"event_type": "TASK_DISPATCHED", "payload": {"workkey": "W123"}}
    injected_event = inject_event(ctx, event)
    assert "_trace" in injected_event
    assert injected_event["_trace"]["traceparent"] == ctx.to_traceparent()

    extracted_event = extract_event(injected_event)
    assert extracted_event is not None
    assert extracted_event.trace_id == ctx.trace_id


def test_contextvar_trace_scope():
    assert current_trace_context() is None

    root = TraceContext.new_root()
    with trace_scope(root):
        active = current_trace_context()
        assert active is not None
        assert active.trace_id == root.trace_id
        assert active.span_id == root.span_id

        # Nested scope with child span
        child = active.child_span()
        with trace_scope(child):
            nested = current_trace_context()
            assert nested.trace_id == root.trace_id
            assert nested.span_id == child.span_id
            assert nested.parent_span_id == root.span_id

        # Restored to root
        restored = current_trace_context()
        assert restored.span_id == root.span_id

    # Exited all scopes
    assert current_trace_context() is None


def test_trace_context_cli(capsys, monkeypatch):
    from courier_core.trace_context import main

    # Generate
    monkeypatch.setattr("sys.argv", ["trace_context.py", "generate"])
    main()
    out1 = capsys.readouterr().out
    assert "traceparent: 00-" in out1

    # Extract traceparent from output
    line = [l for l in out1.splitlines() if l.startswith("traceparent: ")][0]
    tp = line.split("traceparent: ")[1].strip()

    # Parse
    monkeypatch.setattr("sys.argv", ["trace_context.py", "parse", "--traceparent", tp])
    main()
    out2 = capsys.readouterr().out
    parsed_json = json.loads(out2)
    assert len(parsed_json["trace_id"]) == 32
