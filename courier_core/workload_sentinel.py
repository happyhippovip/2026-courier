"""Dynamic Workload Profiler and Anomaly Detection Sentinel for Courier Symphony.

Provides sliding-window statistical telemetry profiling, z-score latency anomaly detection,
burst-failure worker quarantine recommendations, and resource consumption guards.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertCode(str, Enum):
    BURST_FAILURE = "BURST_FAILURE"
    LATENCY_ANOMALY = "LATENCY_ANOMALY"
    RESOURCE_SPIKE = "RESOURCE_SPIKE"
    STALLED_WORKER = "STALLED_WORKER"


class ActionRecommendation(str, Enum):
    NONE = "NONE"
    THROTTLE = "THROTTLE"
    QUARANTINE_WORKER = "QUARANTINE_WORKER"
    PAUSE_LANE = "PAUSE_LANE"


@dataclass
class TaskMetric:
    task_id: str
    task_type: str
    worker_id: str
    duration_ms: float
    status: str  # "SUCCESS" or "FAILED"
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskMetric:
        return cls(**data)


@dataclass
class SentinelAlert:
    alert_id: str
    timestamp: str
    code: AlertCode
    severity: AlertSeverity
    recommendation: ActionRecommendation
    message: str
    target_worker_id: Optional[str] = None
    target_task_type: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["code"] = self.code.value
        data["severity"] = self.severity.value
        data["recommendation"] = self.recommendation.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SentinelAlert:
        return cls(
            alert_id=data["alert_id"],
            timestamp=data["timestamp"],
            code=AlertCode(data["code"]),
            severity=AlertSeverity(data["severity"]),
            recommendation=ActionRecommendation(data["recommendation"]),
            message=data["message"],
            target_worker_id=data.get("target_worker_id"),
            target_task_type=data.get("target_task_type"),
            details=data.get("details", {}),
        )


def _parse_time(ts: str) -> datetime:
    if not ts:
        return datetime.now(timezone.utc)
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return datetime.now(timezone.utc)


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return d0 + d1


class WorkloadSentinel:
    """Sliding-window workload profiler and anomaly detection engine."""

    def __init__(self, store_path: Optional[str] = None, window_seconds: int = 300):
        self.store_path = store_path
        self.window_seconds = window_seconds
        self.metrics: List[TaskMetric] = []
        self.alerts: List[SentinelAlert] = []
        if self.store_path and Path(self.store_path).exists():
            self.load()

    def record_metric(self, metric: TaskMetric) -> None:
        self.metrics.append(metric)

    def _get_window_metrics(
        self,
        task_type: Optional[str] = None,
        worker_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> List[TaskMetric]:
        ref_time = now or datetime.now(timezone.utc)
        cutoff = ref_time - timedelta(seconds=self.window_seconds)

        res = []
        for m in self.metrics:
            m_time = _parse_time(m.timestamp)
            if m_time >= cutoff:
                if task_type and m.task_type != task_type:
                    continue
                if worker_id and m.worker_id != worker_id:
                    continue
                res.append(m)
        return res

    def get_summary(
        self,
        task_type: Optional[str] = None,
        worker_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        window = self._get_window_metrics(task_type=task_type, worker_id=worker_id, now=now)
        total = len(window)
        if total == 0:
            return {
                "total_runs": 0,
                "success_runs": 0,
                "fail_runs": 0,
                "error_rate_pct": 0.0,
                "duration_mean": 0.0,
                "duration_stddev": 0.0,
                "duration_p50": 0.0,
                "duration_p95": 0.0,
                "duration_p99": 0.0,
                "avg_cpu": 0.0,
                "avg_memory_mb": 0.0,
            }

        successes = sum(1 for m in window if m.status == "SUCCESS")
        fails = total - successes
        err_rate = (fails / total) * 100.0

        durations = [m.duration_ms for m in window]
        mean_dur = sum(durations) / total
        variance = sum((d - mean_dur) ** 2 for d in durations) / total
        std_dur = math.sqrt(variance)

        cpus = [m.cpu_percent for m in window]
        mems = [m.memory_mb for m in window]

        return {
            "total_runs": total,
            "success_runs": successes,
            "fail_runs": fails,
            "error_rate_pct": round(err_rate, 2),
            "duration_mean": round(mean_dur, 2),
            "duration_stddev": round(std_dur, 2),
            "duration_p50": round(_percentile(durations, 0.50), 2),
            "duration_p95": round(_percentile(durations, 0.95), 2),
            "duration_p99": round(_percentile(durations, 0.99), 2),
            "avg_cpu": round(sum(cpus) / total, 2),
            "avg_memory_mb": round(sum(mems) / total, 2),
        }

    def analyze_anomalies(self, now: Optional[datetime] = None) -> List[SentinelAlert]:
        ref_time = now or datetime.now(timezone.utc)
        window = self._get_window_metrics(now=ref_time)
        new_alerts: List[SentinelAlert] = []

        if not window:
            return new_alerts

        # 1. Latency Anomaly Detection per task_type
        task_types = {m.task_type for m in window}
        for tt in task_types:
            tt_metrics = [m for m in window if m.task_type == tt]
            if len(tt_metrics) >= 5:
                durations = [m.duration_ms for m in tt_metrics]
                mean_dur = sum(durations) / len(durations)
                variance = sum((d - mean_dur) ** 2 for d in durations) / len(durations)
                std_dur = math.sqrt(variance)

                if std_dur > 0.01:
                    for m in tt_metrics:
                        z = (m.duration_ms - mean_dur) / std_dur
                        if z >= 3.0:
                            sev = AlertSeverity.CRITICAL if z >= 4.5 else AlertSeverity.WARNING
                            alert = SentinelAlert(
                                alert_id=f"alt-lat-{uuid.uuid4().hex[:8]}",
                                timestamp=ref_time.isoformat(),
                                code=AlertCode.LATENCY_ANOMALY,
                                severity=sev,
                                recommendation=ActionRecommendation.THROTTLE,
                                message=f"Latency outlier detected for task '{m.task_id}' (type '{tt}'): duration {m.duration_ms:.1f}ms exceeds baseline mean {mean_dur:.1f}ms (z-score: {z:.2f})",
                                target_worker_id=m.worker_id,
                                target_task_type=tt,
                                details={"z_score": round(z, 2), "duration_ms": m.duration_ms, "mean": round(mean_dur, 2)},
                            )
                            new_alerts.append(alert)

        # 2. Burst Failure Detection per worker
        workers = {m.worker_id for m in window}
        for wid in workers:
            w_metrics = [m for m in window if m.worker_id == wid]
            if len(w_metrics) >= 3:
                fails = sum(1 for m in w_metrics if m.status == "FAILED")
                fail_ratio = fails / len(w_metrics)
                if fail_ratio >= 0.5:
                    alert = SentinelAlert(
                        alert_id=f"alt-fail-{uuid.uuid4().hex[:8]}",
                        timestamp=ref_time.isoformat(),
                        code=AlertCode.BURST_FAILURE,
                        severity=AlertSeverity.CRITICAL,
                        recommendation=ActionRecommendation.QUARANTINE_WORKER,
                        message=f"Burst failure rate detected on worker '{wid}': {fails}/{len(w_metrics)} tasks failed ({fail_ratio*100:.1f}%)",
                        target_worker_id=wid,
                        details={"fails": fails, "total": len(w_metrics), "fail_ratio": round(fail_ratio, 2)},
                    )
                    new_alerts.append(alert)

        # 3. Resource Spike Detection
        for m in window:
            # Memory spike check (>1000MB or > 4x average)
            if m.memory_mb >= 1000.0 or m.cpu_percent >= 90.0:
                alert = SentinelAlert(
                    alert_id=f"alt-res-{uuid.uuid4().hex[:8]}",
                    timestamp=ref_time.isoformat(),
                    code=AlertCode.RESOURCE_SPIKE,
                    severity=AlertSeverity.WARNING,
                    recommendation=ActionRecommendation.THROTTLE,
                    message=f"Resource consumption spike on task '{m.task_id}' ({m.task_type}) on worker '{m.worker_id}': Memory={m.memory_mb:.1f}MB, CPU={m.cpu_percent:.1f}%",
                    target_worker_id=m.worker_id,
                    target_task_type=m.task_type,
                    details={"memory_mb": m.memory_mb, "cpu_percent": m.cpu_percent},
                )
                new_alerts.append(alert)

        self.alerts.extend(new_alerts)
        return new_alerts

    def save(self) -> None:
        if not self.store_path:
            return
        p = Path(self.store_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "window_seconds": self.window_seconds,
            "metrics": [m.to_dict() for m in self.metrics],
            "alerts": [a.to_dict() for a in self.alerts],
        }
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self) -> None:
        if not self.store_path or not Path(self.store_path).exists():
            return
        raw = json.loads(Path(self.store_path).read_text(encoding="utf-8"))
        self.window_seconds = raw.get("window_seconds", self.window_seconds)
        self.metrics = [TaskMetric.from_dict(m) for m in raw.get("metrics", [])]
        self.alerts = [SentinelAlert.from_dict(a) for a in raw.get("alerts", [])]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Dynamic Workload Profiler and Anomaly Detection Sentinel")
    parser.add_argument("--store", default="registries/workload_profile.json", help="Store JSON path")
    parser.add_argument("--window", type=int, default=300, help="Sliding window in seconds")

    sub = parser.add_subparsers(dest="subcommand", required=True)

    # record
    p_rec = sub.add_parser("record", help="Record task metric")
    p_rec.add_argument("--task-id", required=True)
    p_rec.add_argument("--task-type", required=True)
    p_rec.add_argument("--worker-id", required=True)
    p_rec.add_argument("--duration-ms", type=float, required=True)
    p_rec.add_argument("--status", choices=["SUCCESS", "FAILED"], default="SUCCESS")
    p_rec.add_argument("--cpu", type=float, default=0.0)
    p_rec.add_argument("--memory", type=float, default=0.0)

    # inspect
    p_ins = sub.add_parser("inspect", help="Inspect workload profile summary")
    p_ins.add_argument("--task-type", default=None)
    p_ins.add_argument("--worker-id", default=None)

    # analyze
    sub.add_parser("analyze", help="Analyze anomalies in current sliding window")

    # alerts
    sub.add_parser("alerts", help="List active alerts")

    args = parser.parse_args(argv)
    sentinel = WorkloadSentinel(store_path=args.store, window_seconds=args.window)

    if args.subcommand == "record":
        metric = TaskMetric(
            task_id=args.task_id,
            task_type=args.task_type,
            worker_id=args.worker_id,
            duration_ms=args.duration_ms,
            status=args.status,
            cpu_percent=args.cpu,
            memory_mb=args.memory,
        )
        sentinel.record_metric(metric)
        sentinel.save()
        print(f"RECORDED task {args.task_id} ({args.task_type}) on {args.worker_id}")
        return 0

    elif args.subcommand == "inspect":
        summary = sentinel.get_summary(task_type=args.task_type, worker_id=args.worker_id)
        print(f"Workload Profile Summary (task_type={args.task_type}, worker_id={args.worker_id}):")
        print(json.dumps(summary, indent=2))
        return 0

    elif args.subcommand == "analyze":
        alerts = sentinel.analyze_anomalies()
        sentinel.save()
        print(f"ANALYZE completed. Generated {len(alerts)} ALERTS:")
        for a in alerts:
            print(f"[{a.severity.value}] {a.code.value} -> {a.recommendation.value}: {a.message}")
        return 0

    elif args.subcommand == "alerts":
        print(f"Total alerts recorded: {len(sentinel.alerts)}")
        for a in sentinel.alerts:
            print(f"[{a.severity.value}] {a.code.value}: {a.message}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
