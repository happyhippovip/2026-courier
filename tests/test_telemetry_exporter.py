"""Tests for courier_core.telemetry_exporter - OpenTelemetry Metric & Span Exporter."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from courier_core.telemetry_exporter import (
    OpenTelemetryExporter,
    MetricType,
    SpanStatus,
    TelemetryMetric,
    TelemetrySpan,
    InvalidMetricError,
)


@pytest.fixture
def exporter(tmp_path: Path) -> OpenTelemetryExporter:
    sink_file = tmp_path / "telemetry_sink.jsonl"
    return OpenTelemetryExporter(service_name="courier-symphony", sink_file=sink_file)


def test_record_counter_and_gauge(exporter: OpenTelemetryExporter):
    exporter.record_counter("worker.tasks.completed", value=5, attributes={"lane": "L3", "worker": "win-1"})
    exporter.record_gauge("worker.slots.in_use", value=2.0, attributes={"host": "titan-win"})

    assert len(exporter.buffer_metrics) == 2
    c = exporter.buffer_metrics[0]
    assert c.name == "worker.tasks.completed"
    assert c.metric_type == MetricType.COUNTER
    assert c.value == 5
    assert c.attributes["lane"] == "L3"

    g = exporter.buffer_metrics[1]
    assert g.name == "worker.slots.in_use"
    assert g.metric_type == MetricType.GAUGE
    assert g.value == 2.0


def test_histogram_latency_recording(exporter: OpenTelemetryExporter):
    for latency in [10.0, 25.0, 50.0, 100.0]:
        exporter.record_histogram("task.execution.duration_ms", value=latency, attributes={"status": "OK"})

    assert len(exporter.buffer_metrics) == 4
    # Evaluate aggregate
    summary = exporter.get_histogram_summary("task.execution.duration_ms")
    assert summary["count"] == 4
    assert summary["sum"] == 185.0
    assert summary["min"] == 10.0
    assert summary["max"] == 100.0


def test_otlp_json_export_structure(exporter: OpenTelemetryExporter):
    exporter.record_counter("courier.events.processed", value=100, attributes={"env": "prod"})
    otlp = exporter.to_otlp_json()

    assert "resourceMetrics" in otlp
    res = otlp["resourceMetrics"][0]["resource"]
    attrs = {a["key"]: a["value"]["stringValue"] for a in res["attributes"]}
    assert attrs["service.name"] == "courier-symphony"

    metric_data = otlp["resourceMetrics"][0]["scopeMetrics"][0]["metrics"][0]
    assert metric_data["name"] == "courier.events.processed"
    assert "sum" in metric_data
    dp = metric_data["sum"]["dataPoints"][0]
    assert dp["asInt"] == 100


def test_trace_span_recording_and_linkage(exporter: OpenTelemetryExporter):
    span = TelemetrySpan(
        name="dispatch_task",
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        span_id="00f067aa0ba902b7",
        parent_span_id="5fb397be34d23b0f",
        duration_ms=45.2,
        status=SpanStatus.OK,
        attributes={"task_id": "T123"},
    )
    exporter.record_span(span)
    assert len(exporter.buffer_spans) == 1

    otlp = exporter.to_otlp_json()
    assert "resourceSpans" in otlp
    spans_data = otlp["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert len(spans_data) == 1
    assert spans_data[0]["name"] == "dispatch_task"
    assert spans_data[0]["traceId"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert spans_data[0]["spanId"] == "00f067aa0ba902b7"


def test_buffer_flush_to_file(exporter: OpenTelemetryExporter, tmp_path: Path):
    sink = tmp_path / "telemetry_sink.jsonl"
    exporter.sink_file = sink

    exporter.record_counter("test.flush.metric", value=1)
    exporter.record_span(
        TelemetrySpan(
            name="test_span",
            trace_id="1" * 32,
            span_id="2" * 16,
            duration_ms=10.0,
            status=SpanStatus.OK,
        )
    )

    assert len(exporter.buffer_metrics) == 1
    assert len(exporter.buffer_spans) == 1

    flushed_count = exporter.flush()
    assert flushed_count == 2
    assert len(exporter.buffer_metrics) == 0
    assert len(exporter.buffer_spans) == 0

    assert sink.exists()
    lines = [json.loads(line) for line in sink.read_text(encoding="utf-8").strip().splitlines()]
    assert len(lines) == 2


def test_metric_name_and_attribute_sanitization(exporter: OpenTelemetryExporter):
    # Invalid names
    for bad_name in ["bad name with space", "123numeric_start", "special$char", ""]:
        with pytest.raises(InvalidMetricError):
            exporter.record_counter(bad_name, value=1)

    # Valid names
    for good_name in ["valid.metric.name", "system_cpu_usage", "http-requests-total"]:
        exporter.record_counter(good_name, value=1)
    assert len(exporter.buffer_metrics) == 3


def test_cli_telemetry(tmp_path: Path, monkeypatch, capsys):
    from courier_core.telemetry_exporter import main

    sink = tmp_path / "cli_sink.jsonl"

    # Record metric via CLI
    monkeypatch.setattr(
        "sys.argv",
        [
            "telemetry_exporter.py",
            "--sink", str(sink),
            "record-metric",
            "--name", "cli.test.counter",
            "--type", "COUNTER",
            "--value", "42",
            "--attributes", "env=test,host=local",
        ],
    )
    main()

    # Status via CLI
    monkeypatch.setattr(
        "sys.argv",
        ["telemetry_exporter.py", "--sink", str(sink), "status"],
    )
    main()
    out = capsys.readouterr().out
    assert "cli.test.counter" in out
