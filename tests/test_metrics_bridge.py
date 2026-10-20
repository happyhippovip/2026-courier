"""Tests for courier_core.metrics_bridge (Observability Prometheus / OpenMetrics Bridge)."""

import pytest
from pathlib import Path
from courier_core.metrics_bridge import (
    MetricRegistry,
    MetricType,
    Counter,
    Gauge,
    Summary,
    ClusterMetricsBridge,
    format_prometheus_exposition,
    main,
)
from courier_core.backpressure_controller import BackpressureController
from courier_core.replica_coordinator import ReplicaCoordinator
from courier_core.fencing_token import FencingTokenManager


def test_metric_registry_counters_and_gauges():
    registry = MetricRegistry()
    c = registry.counter("courier_tasks_total", "Total tasks processed")
    g = registry.gauge("courier_active_nodes", "Number of active nodes")

    c.inc(1.0, labels={"status": "SUCCESS", "worker": "win-1"})
    c.inc(2.0, labels={"status": "SUCCESS", "worker": "win-1"})
    c.inc(1.0, labels={"status": "FAILED", "worker": "win-1"})
    g.set(5.0, labels={"cluster": "production"})

    output = format_prometheus_exposition(registry)

    assert "# HELP courier_tasks_total Total tasks processed" in output
    assert "# TYPE courier_tasks_total counter" in output
    assert 'courier_tasks_total{status="SUCCESS",worker="win-1"} 3.0' in output
    assert 'courier_tasks_total{status="FAILED",worker="win-1"} 1.0' in output
    assert "# TYPE courier_active_nodes gauge" in output
    assert 'courier_active_nodes{cluster="production"} 5.0' in output


def test_histogram_quantiles_rendering():
    registry = MetricRegistry()
    s = registry.summary("courier_task_duration_ms", "Task execution duration in milliseconds")

    for val in [10.0, 20.0, 30.0, 40.0, 50.0, 100.0]:
        s.observe(val, labels={"task_type": "compile"})

    output = format_prometheus_exposition(registry)

    assert "# TYPE courier_task_duration_ms summary" in output
    assert 'courier_task_duration_ms{quantile="0.5",task_type="compile"}' in output
    assert 'courier_task_duration_ms{quantile="0.9",task_type="compile"}' in output
    assert 'courier_task_duration_ms_count{task_type="compile"} 6' in output
    assert 'courier_task_duration_ms_sum{task_type="compile"} 250.0' in output


def test_collector_bridge_snapshot_aggregation(tmp_path):
    ft_file = tmp_path / "fences.json"
    fence_mgr = FencingTokenManager(state_path=ft_file)
    rec = fence_mgr.acquire("res-core", "worker-1", ttl_seconds=60)
    fence_mgr.validate_and_commit("res-core", rec.generation)

    bp = BackpressureController(initial_rate=15.0)
    bp.acquire_permit("task-active-1")

    coord = ReplicaCoordinator(node_id="lead-node", store_path=str(tmp_path / "rep.json"))
    coord.register_peer("peer-x", "http://10.0.0.10:8000")

    bridge = ClusterMetricsBridge(
        fencing_mgr=fence_mgr,
        backpressure_ctrl=bp,
        replica_coord=coord,
    )

    metrics_text = bridge.collect_and_export()
    assert "courier_backpressure_rate_permits_per_sec 15.0" in metrics_text
    assert "courier_inflight_tasks 1" in metrics_text
    assert "courier_active_nodes 2" in metrics_text
    assert "courier_fencing_generation" in metrics_text


def test_http_scrape_handler(tmp_path):
    bridge = ClusterMetricsBridge()
    registry = bridge.registry
    counter = registry.counter("http_requests_total", "Total requests")
    counter.inc(10.0)

    # Simulate scrape request
    status, headers, body = bridge.handle_scrape_request()
    assert status == 200
    assert headers["Content-Type"] == "text/plain; version=0.0.4; charset=utf-8"
    assert "http_requests_total 10.0" in body


def test_export_metrics_file_and_persistence(tmp_path):
    out_file = tmp_path / "metrics.prom"
    bridge = ClusterMetricsBridge(export_path=str(out_file))
    bridge.registry.gauge("system_health_ratio").set(1.0)

    bridge.export_to_file()
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "system_health_ratio 1.0" in content


def test_cli_metrics_bridge(tmp_path, capsys):
    metrics_file = tmp_path / "cli_metrics.prom"

    # Export CLI
    rc1 = main(["export", "--out", str(metrics_file)])
    assert rc1 == 0
    assert "EXPORTED" in capsys.readouterr().out
    assert metrics_file.exists()

    # Inspect CLI
    rc2 = main(["inspect"])
    assert rc2 == 0
    out = capsys.readouterr().out
    assert "courier_backpressure_rate_permits_per_sec" in out or "# TYPE" in out
