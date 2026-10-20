"""Tests for courier_core.workload_sentinel (Dynamic Workload Profiler & Anomaly Sentinel)."""

import json
import pytest
from datetime import datetime, timezone, timedelta
from courier_core.workload_sentinel import (
    WorkloadSentinel,
    TaskMetric,
    SentinelAlert,
    AlertSeverity,
    AlertCode,
    ActionRecommendation,
    main,
)


def test_record_execution_metric_and_window_aggregation(tmp_path):
    store_file = tmp_path / "sentinel_profile.json"
    sentinel = WorkloadSentinel(store_path=str(store_file), window_seconds=300)

    now = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
    for i in range(10):
        t = now + timedelta(seconds=i * 5)
        sentinel.record_metric(
            TaskMetric(
                task_id=f"T{i}",
                task_type="build_package",
                worker_id="worker-win-1",
                duration_ms=100.0 + (i % 3) * 10.0,
                status="SUCCESS",
                cpu_percent=15.0,
                memory_mb=64.0,
                timestamp=t.isoformat(),
            )
        )

    summary = sentinel.get_summary(task_type="build_package", now=now + timedelta(seconds=50))
    assert summary["total_runs"] == 10
    assert summary["success_runs"] == 10
    assert summary["fail_runs"] == 0
    assert summary["error_rate_pct"] == 0.0
    assert 100.0 <= summary["duration_p50"] <= 120.0
    assert summary["duration_mean"] > 0


def test_zscore_latency_anomaly_detection(tmp_path):
    sentinel = WorkloadSentinel(store_path=str(tmp_path / "profile.json"), window_seconds=600)
    now = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)

    # Establish baseline: 20 runs around 100ms
    for i in range(20):
        sentinel.record_metric(
            TaskMetric(
                task_id=f"B{i}",
                task_type="index_evidence",
                worker_id="worker-1",
                duration_ms=100.0 + (i % 5) - 2.0,
                status="SUCCESS",
                cpu_percent=10.0,
                memory_mb=50.0,
                timestamp=(now + timedelta(seconds=i * 2)).isoformat(),
            )
        )

    # Inject extreme outlier
    outlier = TaskMetric(
        task_id="OUTLIER_1",
        task_type="index_evidence",
        worker_id="worker-1",
        duration_ms=1500.0,
        status="SUCCESS",
        cpu_percent=20.0,
        memory_mb=60.0,
        timestamp=(now + timedelta(seconds=50)).isoformat(),
    )
    sentinel.record_metric(outlier)

    alerts = sentinel.analyze_anomalies(now=now + timedelta(seconds=55))
    latency_alerts = [a for a in alerts if a.code == AlertCode.LATENCY_ANOMALY]
    assert len(latency_alerts) >= 1
    alert = latency_alerts[0]
    assert alert.severity in (AlertSeverity.WARNING, AlertSeverity.CRITICAL)
    assert alert.target_task_type == "index_evidence"
    assert "outlier" in alert.message.lower() or "z-score" in alert.message.lower()


def test_burst_failure_detection_and_quarantine_recommendation(tmp_path):
    sentinel = WorkloadSentinel(store_path=str(tmp_path / "profile.json"), window_seconds=300)
    now = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)

    # Worker-bad experiences repeated fast failures
    for i in range(6):
        sentinel.record_metric(
            TaskMetric(
                task_id=f"FAIL_{i}",
                task_type="network_sync",
                worker_id="worker-faulty-node",
                duration_ms=50.0,
                status="FAILED",
                cpu_percent=5.0,
                memory_mb=30.0,
                timestamp=(now + timedelta(seconds=i * 2)).isoformat(),
            )
        )

    alerts = sentinel.analyze_anomalies(now=now + timedelta(seconds=20))
    burst_alerts = [a for a in alerts if a.code == AlertCode.BURST_FAILURE]
    assert len(burst_alerts) >= 1
    assert any(a.recommendation == ActionRecommendation.QUARANTINE_WORKER for a in burst_alerts)
    assert any("worker-faulty-node" in a.message for a in burst_alerts)


def test_resource_consumption_anomaly(tmp_path):
    sentinel = WorkloadSentinel(store_path=str(tmp_path / "profile.json"), window_seconds=300)
    now = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)

    # Baseline 10 runs with 40MB memory
    for i in range(10):
        sentinel.record_metric(
            TaskMetric(
                task_id=f"NORM_{i}",
                task_type="hash_cache",
                worker_id="worker-1",
                duration_ms=80.0,
                status="SUCCESS",
                cpu_percent=12.0,
                memory_mb=40.0,
                timestamp=(now + timedelta(seconds=i * 3)).isoformat(),
            )
        )

    # Massive memory jump (e.g. 2500 MB)
    spike = TaskMetric(
        task_id="SPIKE_1",
        task_type="hash_cache",
        worker_id="worker-1",
        duration_ms=90.0,
        status="SUCCESS",
        cpu_percent=95.0,
        memory_mb=2500.0,
        timestamp=(now + timedelta(seconds=35)).isoformat(),
    )
    sentinel.record_metric(spike)

    alerts = sentinel.analyze_anomalies(now=now + timedelta(seconds=40))
    res_alerts = [a for a in alerts if a.code == AlertCode.RESOURCE_SPIKE]
    assert len(res_alerts) >= 1
    assert res_alerts[0].recommendation == ActionRecommendation.THROTTLE


def test_persistence_profile_export_and_alert_history(tmp_path):
    store_file = tmp_path / "persisted_profile.json"
    sentinel1 = WorkloadSentinel(store_path=str(store_file), window_seconds=300)
    now = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)

    sentinel1.record_metric(
        TaskMetric(
            task_id="P1",
            task_type="backup",
            worker_id="worker-a",
            duration_ms=250.0,
            status="SUCCESS",
            cpu_percent=10.0,
            memory_mb=100.0,
            timestamp=now.isoformat(),
        )
    )
    sentinel1.save()

    # Reopen from disk
    sentinel2 = WorkloadSentinel(store_path=str(store_file), window_seconds=300)
    summary = sentinel2.get_summary(task_type="backup", now=now)
    assert summary["total_runs"] == 1
    assert summary["duration_mean"] == 250.0


def test_cli_workload_sentinel(tmp_path, capsys):
    profile_path = tmp_path / "cli_profile.json"

    # Record metric via CLI
    rc1 = main([
        "--store", str(profile_path),
        "record",
        "--task-id", "CLI_1",
        "--task-type", "compile",
        "--worker-id", "win-box",
        "--duration-ms", "150.5",
        "--status", "SUCCESS",
        "--cpu", "25.0",
        "--memory", "128.0",
    ])
    assert rc1 == 0
    assert "RECORDED" in capsys.readouterr().out

    # Inspect via CLI
    rc2 = main(["--store", str(profile_path), "inspect", "--task-type", "compile"])
    assert rc2 == 0
    out2 = capsys.readouterr().out
    assert "total_runs" in out2
    assert "compile" in out2

    # Analyze via CLI
    rc3 = main(["--store", str(profile_path), "analyze"])
    assert rc3 == 0
    out3 = capsys.readouterr().out
    assert "ALERTS" in out3 or "alerts" in out3.lower()
