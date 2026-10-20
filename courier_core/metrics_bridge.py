"""Real-Time Observability Prometheus and OpenTelemetry Metrics Bridge for Courier Symphony.

Provides standard OpenMetrics / Prometheus exposition format generation for gauges, counters,
and summaries, aggregating health, backpressure, fencing, and replication telemetry.
"""

from __future__ import annotations

import argparse
import http.server
import json
import math
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    SUMMARY = "summary"


def _format_labels(labels: Optional[Dict[str, str]], extra_labels: Optional[Dict[str, str]] = None) -> str:
    merged: Dict[str, str] = {}
    if extra_labels:
        merged.update(extra_labels)
    if labels:
        merged.update(labels)
    if not merged:
        return ""
    sorted_pairs = [f'{k}="{v}"' for k, v in sorted(merged.items())]
    return "{" + ",".join(sorted_pairs) + "}"


class Counter:
    """Monotonically increasing cumulative metric counter."""

    def __init__(self, name: str, help_text: str = ""):
        self.name = name
        self.help_text = help_text
        self.metric_type = MetricType.COUNTER
        self.values: Dict[Tuple[Tuple[str, str], ...], float] = {}

    def inc(self, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        key = tuple(sorted((labels or {}).items()))
        self.values[key] = self.values.get(key, 0.0) + value


class Gauge:
    """Metric representing a single numerical value that can arbitrarily go up and down."""

    def __init__(self, name: str, help_text: str = ""):
        self.name = name
        self.help_text = help_text
        self.metric_type = MetricType.GAUGE
        self.values: Dict[Tuple[Tuple[str, str], ...], float] = {}

    def set(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        key = tuple(sorted((labels or {}).items()))
        self.values[key] = float(value)

    def inc(self, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        key = tuple(sorted((labels or {}).items()))
        self.values[key] = self.values.get(key, 0.0) + value

    def dec(self, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        key = tuple(sorted((labels or {}).items()))
        self.values[key] = self.values.get(key, 0.0) - value


class Summary:
    """Samples observations and provides percentile / quantile summaries."""

    def __init__(self, name: str, help_text: str = ""):
        self.name = name
        self.help_text = help_text
        self.metric_type = MetricType.SUMMARY
        self.observations: Dict[Tuple[Tuple[str, str], ...], List[float]] = {}

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        key = tuple(sorted((labels or {}).items()))
        if key not in self.observations:
            self.observations[key] = []
        self.observations[key].append(float(value))


class MetricRegistry:
    """Registry maintaining collection of registered metric families."""

    def __init__(self):
        self._metrics: Dict[str, Any] = {}

    def counter(self, name: str, help_text: str = "") -> Counter:
        if name not in self._metrics:
            self._metrics[name] = Counter(name, help_text)
        return self._metrics[name]

    def gauge(self, name: str, help_text: str = "") -> Gauge:
        if name not in self._metrics:
            self._metrics[name] = Gauge(name, help_text)
        return self._metrics[name]

    def summary(self, name: str, help_text: str = "") -> Summary:
        if name not in self._metrics:
            self._metrics[name] = Summary(name, help_text)
        return self._metrics[name]

    def get_all(self) -> List[Any]:
        return list(self._metrics.values())


def _calc_percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[int(f)] * (c - k) + sorted_vals[int(c)] * (k - f)


def format_prometheus_exposition(registry: MetricRegistry) -> str:
    """Render registered metrics into official Prometheus text exposition format."""
    lines: List[str] = []

    for metric in registry.get_all():
        if metric.help_text:
            lines.append(f"# HELP {metric.name} {metric.help_text}")
        lines.append(f"# TYPE {metric.name} {metric.metric_type.value}")

        if metric.metric_type in (MetricType.COUNTER, MetricType.GAUGE):
            if not metric.values:
                lines.append(f"{metric.name} 0.0")
            for label_tuple, val in sorted(metric.values.items()):
                label_dict = dict(label_tuple)
                lbl_str = _format_labels(label_dict)
                lines.append(f"{metric.name}{lbl_str} {val}")

        elif metric.metric_type == MetricType.SUMMARY:
            for label_tuple, obs_list in sorted(metric.observations.items()):
                label_dict = dict(label_tuple)
                sorted_vals = sorted(obs_list)
                total_sum = sum(sorted_vals)
                total_count = len(sorted_vals)

                for q in [0.5, 0.9, 0.95, 0.99]:
                    pval = _calc_percentile(sorted_vals, q)
                    lbl_str = _format_labels(label_dict, extra_labels={"quantile": str(q)})
                    lines.append(f"{metric.name}{lbl_str} {pval}")

                cnt_lbl = _format_labels(label_dict)
                lines.append(f"{metric.name}_sum{cnt_lbl} {total_sum}")
                lines.append(f"{metric.name}_count{cnt_lbl} {total_count}")

    lines.append("")  # Trailing newline required by Prometheus spec
    return "\n".join(lines)


class ClusterMetricsBridge:
    """Bridges cluster components into the observability metrics registry."""

    def __init__(
        self,
        fencing_mgr: Optional[Any] = None,
        backpressure_ctrl: Optional[Any] = None,
        replica_coord: Optional[Any] = None,
        export_path: Optional[str] = None,
    ):
        self.fencing_mgr = fencing_mgr
        self.backpressure_ctrl = backpressure_ctrl
        self.replica_coord = replica_coord
        self.export_path = export_path
        self.registry = MetricRegistry()

    def collect_and_export(self) -> str:
        """Poll component telemetry and update registered gauges."""
        # Backpressure metrics
        if self.backpressure_ctrl is not None:
            self.registry.gauge("courier_backpressure_rate_permits_per_sec", "Current rate limit permits").set(
                self.backpressure_ctrl.current_rate
            )
            self.registry.gauge("courier_inflight_tasks", "Active inflight tasks").set(
                self.backpressure_ctrl.inflight_count
            )

        # Replica coordinator metrics
        if self.replica_coord is not None:
            self.registry.gauge("courier_active_nodes", "Active cluster replica nodes").set(
                self.replica_coord.active_node_count()
            )
            self.registry.gauge("courier_replication_sequence", "Current monotonic replication sequence").set(
                self.replica_coord.current_sequence
            )

        # Fencing token metrics
        if self.fencing_mgr is not None:
            for res_id, rec in getattr(self.fencing_mgr, "_resources", {}).items():
                self.registry.gauge(
                    "courier_fencing_generation",
                    "Highest fencing generation per resource",
                ).set(rec.generation, labels={"resource": res_id})

        return format_prometheus_exposition(self.registry)

    def export_to_file(self) -> None:
        if not self.export_path:
            return
        p = Path(self.export_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        content = self.collect_and_export()
        p.write_text(content, encoding="utf-8")

    def handle_scrape_request(self) -> Tuple[int, Dict[str, str], str]:
        body = self.collect_and_export()
        headers = {
            "Content-Type": "text/plain; version=0.0.4; charset=utf-8",
            "Content-Length": str(len(body.encode("utf-8"))),
        }
        return (200, headers, body)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Courier Observability Metrics Bridge CLI")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    # export
    p_exp = sub.add_parser("export", help="Export metrics snapshot to file")
    p_exp.add_argument("--out", default="registries/metrics.prom", help="Output path")

    # inspect
    sub.add_parser("inspect", help="Display formatted Prometheus metrics to stdout")

    args = parser.parse_args(argv)
    bridge = ClusterMetricsBridge(export_path=getattr(args, "out", None))

    # Initialize default gauges for demonstration
    bridge.registry.gauge("courier_backpressure_rate_permits_per_sec").set(10.0)
    bridge.registry.gauge("courier_active_nodes").set(1.0)

    if args.subcommand == "export":
        bridge.export_to_file()
        print(f"EXPORTED Prometheus metrics to: {args.out}")
        return 0

    elif args.subcommand == "inspect":
        output = bridge.collect_and_export()
        print(output)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
