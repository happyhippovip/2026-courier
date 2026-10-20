"""Structured Telemetry & OpenTelemetry Metric & Span Exporter.

Compliant with OpenTelemetry Protocol (OTLP) JSON schema. Supports Counter,
Gauge, and Histogram metrics, span tracing correlation, and buffered file sink.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import os
from pathlib import Path
import re
import time
from typing import Any

_METRIC_NAME_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]*$")


class InvalidMetricError(ValueError):
    """Raised when a metric name or attribute fails specification validation."""


class MetricType(str, Enum):
    """OpenTelemetry Metric Types."""

    COUNTER = "COUNTER"
    GAUGE = "GAUGE"
    HISTOGRAM = "HISTOGRAM"


class SpanStatus(str, Enum):
    """OpenTelemetry Span Status."""

    OK = "OK"
    ERROR = "ERROR"
    UNSET = "UNSET"


def _now_ns() -> int:
    return time.time_ns()


@dataclass
class TelemetryMetric:
    """Descriptor for a recorded numeric metric."""

    name: str
    metric_type: MetricType
    value: float | int
    unit: str = ""
    description: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    timestamp_ns: int = field(default_factory=_now_ns)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["metric_type"] = self.metric_type.value
        return d


@dataclass
class TelemetrySpan:
    """Descriptor for an OpenTelemetry execution span."""

    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    duration_ms: float = 0.0
    status: SpanStatus = SpanStatus.OK
    attributes: dict[str, Any] = field(default_factory=dict)
    start_time_ns: int = field(default_factory=_now_ns)
    end_time_ns: int = field(default_factory=_now_ns)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


class OpenTelemetryExporter:
    """Exporter collecting metrics and spans with OTLP serialization and disk sink."""

    def __init__(
        self,
        service_name: str = "courier-symphony",
        sink_file: Path | str | None = None,
        max_buffer_size: int = 1000,
    ) -> None:
        self.service_name = service_name
        self.sink_file = Path(sink_file).resolve() if sink_file else None
        self.max_buffer_size = max(10, max_buffer_size)

        self.buffer_metrics: list[TelemetryMetric] = []
        self.buffer_spans: list[TelemetrySpan] = []

    def _validate_name(self, name: str) -> None:
        if not isinstance(name, str) or not _METRIC_NAME_REGEX.match(name):
            raise InvalidMetricError(f"Invalid metric name: {name!r}")

    def _sanitize_attributes(self, attrs: dict[str, Any] | None) -> dict[str, str]:
        if not attrs:
            return {}
        out = {}
        for k, v in list(attrs.items())[:64]:  # Max 64 attributes
            key_str = str(k)[:128]
            val_str = str(v)[:1024]
            out[key_str] = val_str
        return out

    def record_counter(
        self,
        name: str,
        value: int | float = 1,
        attributes: dict[str, Any] | None = None,
        unit: str = "",
        description: str = "",
    ) -> TelemetryMetric:
        self._validate_name(name)
        metric = TelemetryMetric(
            name=name,
            metric_type=MetricType.COUNTER,
            value=value,
            unit=unit,
            description=description,
            attributes=self._sanitize_attributes(attributes),
        )
        self.buffer_metrics.append(metric)
        return metric

    def record_gauge(
        self,
        name: str,
        value: float | int,
        attributes: dict[str, Any] | None = None,
        unit: str = "",
        description: str = "",
    ) -> TelemetryMetric:
        self._validate_name(name)
        metric = TelemetryMetric(
            name=name,
            metric_type=MetricType.GAUGE,
            value=value,
            unit=unit,
            description=description,
            attributes=self._sanitize_attributes(attributes),
        )
        self.buffer_metrics.append(metric)
        return metric

    def record_histogram(
        self,
        name: str,
        value: float | int,
        attributes: dict[str, Any] | None = None,
        unit: str = "ms",
        description: str = "",
    ) -> TelemetryMetric:
        self._validate_name(name)
        metric = TelemetryMetric(
            name=name,
            metric_type=MetricType.HISTOGRAM,
            value=value,
            unit=unit,
            description=description,
            attributes=self._sanitize_attributes(attributes),
        )
        self.buffer_metrics.append(metric)
        return metric

    def record_span(self, span: TelemetrySpan) -> None:
        self.buffer_spans.append(span)

    def get_histogram_summary(self, name: str) -> dict[str, Any]:
        """Aggregate summary metrics for recorded histogram observations."""
        values = [m.value for m in self.buffer_metrics if m.name == name and m.metric_type == MetricType.HISTOGRAM]
        if not values:
            return {"name": name, "count": 0, "sum": 0.0, "min": 0.0, "max": 0.0, "avg": 0.0}

        return {
            "name": name,
            "count": len(values),
            "sum": round(sum(values), 4),
            "min": round(min(values), 4),
            "max": round(max(values), 4),
            "avg": round(sum(values) / len(values), 4),
        }

    def flush(self) -> int:
        """Flush in-memory buffers to sink file and clear memory."""
        if not self.sink_file:
            count = len(self.buffer_metrics) + len(self.buffer_spans)
            self.buffer_metrics.clear()
            self.buffer_spans.clear()
            return count

        self.sink_file.parent.mkdir(parents=True, exist_ok=True)
        items_to_write = []

        for m in self.buffer_metrics:
            items_to_write.append({"type": "metric", "data": m.to_dict()})
        for s in self.buffer_spans:
            items_to_write.append({"type": "span", "data": s.to_dict()})

        with self.sink_file.open("a", encoding="utf-8") as f:
            for item in items_to_write:
                f.write(json.dumps(item) + "\n")

        total_flushed = len(items_to_write)
        self.buffer_metrics.clear()
        self.buffer_spans.clear()
        return total_flushed

    def to_otlp_json(self) -> dict[str, Any]:
        """Convert collected metrics and spans to standard OpenTelemetry Protocol JSON."""
        res_attrs = [
            {"key": "service.name", "value": {"stringValue": self.service_name}},
            {"key": "host.name", "value": {"stringValue": os.environ.get("COMPUTERNAME", "localhost")}},
        ]

        # Build metrics payload
        otlp_metrics = []
        for m in self.buffer_metrics:
            dp_attrs = [{"key": k, "value": {"stringValue": str(v)}} for k, v in m.attributes.items()]
            data_point: dict[str, Any] = {
                "timeUnixNano": str(m.timestamp_ns),
                "attributes": dp_attrs,
            }
            if isinstance(m.value, int):
                data_point["asInt"] = m.value
            else:
                data_point["asDouble"] = float(m.value)

            if m.metric_type == MetricType.COUNTER:
                otlp_metrics.append({
                    "name": m.name,
                    "unit": m.unit,
                    "description": m.description,
                    "sum": {
                        "isMonotonic": True,
                        "aggregationTemporality": 2,  # Cumulative
                        "dataPoints": [data_point],
                    },
                })
            elif m.metric_type == MetricType.GAUGE:
                otlp_metrics.append({
                    "name": m.name,
                    "unit": m.unit,
                    "description": m.description,
                    "gauge": {
                        "dataPoints": [data_point],
                    },
                })
            elif m.metric_type == MetricType.HISTOGRAM:
                otlp_metrics.append({
                    "name": m.name,
                    "unit": m.unit,
                    "description": m.description,
                    "histogram": {
                        "dataPoints": [data_point],
                    },
                })

        # Build spans payload
        otlp_spans = []
        for s in self.buffer_spans:
            span_attrs = [{"key": k, "value": {"stringValue": str(v)}} for k, v in s.attributes.items()]
            otlp_spans.append({
                "traceId": s.trace_id,
                "spanId": s.span_id,
                "parentSpanId": s.parent_span_id or "",
                "name": s.name,
                "startTimeUnixNano": str(s.start_time_ns),
                "endTimeUnixNano": str(s.end_time_ns),
                "attributes": span_attrs,
                "status": {"code": 1 if s.status == SpanStatus.OK else 2},
            })

        out: dict[str, Any] = {}
        if otlp_metrics:
            out["resourceMetrics"] = [{
                "resource": {"attributes": res_attrs},
                "scopeMetrics": [{
                    "scope": {"name": "courier_core.telemetry"},
                    "metrics": otlp_metrics,
                }],
            }]
        if otlp_spans:
            out["resourceSpans"] = [{
                "resource": {"attributes": res_attrs},
                "scopeSpans": [{
                    "scope": {"name": "courier_core.telemetry"},
                    "spans": otlp_spans,
                }],
            }]

        return out


_GLOBAL_EXPORTER: OpenTelemetryExporter | None = None


def get_global_exporter(sink: Path | str | None = None) -> OpenTelemetryExporter:
    global _GLOBAL_EXPORTER
    if _GLOBAL_EXPORTER is None:
        _GLOBAL_EXPORTER = OpenTelemetryExporter(sink_file=sink)
    return _GLOBAL_EXPORTER


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenTelemetry Metric & Span Exporter")
    parser.add_argument("--sink", default=None, help="Sink file path for JSONL persistence")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # record-metric
    m_p = subparsers.add_parser("record-metric", help="Record a numeric metric")
    m_p.add_argument("--name", required=True, help="Metric name")
    m_p.add_argument("--type", choices=["COUNTER", "GAUGE", "HISTOGRAM"], default="COUNTER")
    m_p.add_argument("--value", type=float, required=True, help="Metric value")
    m_p.add_argument("--attributes", default=None, help="Comma-separated k=v pairs")

    # record-span
    s_p = subparsers.add_parser("record-span", help="Record a trace span")
    s_p.add_argument("--name", required=True, help="Span name")
    s_p.add_argument("--trace-id", required=True, help="Trace ID (32 hex)")
    s_p.add_argument("--span-id", required=True, help="Span ID (16 hex)")
    s_p.add_argument("--duration-ms", type=float, default=0.0, help="Duration in ms")

    # status
    subparsers.add_parser("status", help="Get status of telemetry buffers")

    # flush
    subparsers.add_parser("flush", help="Flush buffers to sink file")

    # export-otlp
    subparsers.add_parser("export-otlp", help="Export buffered telemetry in OTLP JSON format")

    args = parser.parse_args()
    exporter = get_global_exporter(args.sink)

    if args.action == "record-metric":
        attrs = {}
        if args.attributes:
            for pair in args.attributes.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    attrs[k.strip()] = v.strip()

        m_type = MetricType[args.type]
        if m_type == MetricType.COUNTER:
            exporter.record_counter(args.name, value=args.value, attributes=attrs)
        elif m_type == MetricType.GAUGE:
            exporter.record_gauge(args.name, value=args.value, attributes=attrs)
        elif m_type == MetricType.HISTOGRAM:
            exporter.record_histogram(args.name, value=args.value, attributes=attrs)
        print(f"Recorded metric {args.name} = {args.value}")
    elif args.action == "record-span":
        span = TelemetrySpan(
            name=args.name,
            trace_id=args.trace_id,
            span_id=args.span_id,
            duration_ms=args.duration_ms,
        )
        exporter.record_span(span)
        print(f"Recorded span {args.name}")
    elif args.action == "status":
        print(json.dumps({
            "service_name": exporter.service_name,
            "buffer_metrics_count": len(exporter.buffer_metrics),
            "buffer_spans_count": len(exporter.buffer_spans),
            "metrics": [m.to_dict() for m in exporter.buffer_metrics],
        }, indent=2))
    elif args.action == "flush":
        n = exporter.flush()
        print(f"Flushed {n} records to {exporter.sink_file}")
    elif args.action == "export-otlp":
        print(json.dumps(exporter.to_otlp_json(), indent=2))


if __name__ == "__main__":
    main()
