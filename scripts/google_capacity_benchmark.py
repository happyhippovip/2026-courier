#!/usr/bin/env python3
"""Google AI 1-Account 24-Hour Capacity & Economics Benchmark Engine (Real Telemetry Mode).

Measures how much real, useful, accepted production one legitimately subscribed
Google AI account can produce over up to 24 hours.

Strict Real Telemetry Directives:
- CAPACITY_SOURCE must be strictly one of: PROVIDER_OBSERVED | UI_OBSERVED | UNKNOWN.
- NEVER decrement capacity artificially or infer consumption from jobs.
- All historical/synthetic capacity entries are marked CAPACITY_EVIDENCE="UNVERIFIED".
- Real elapsed time, real task completions, real accepted assets, and real limit events are measured.
- REAL_REVENUE = 0 EUR until received.
- AUTONOMOUS_ADDITIONAL_SPEND_LIMIT = 0 EUR.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

COURIER_DIR = Path(__file__).resolve().parent.parent
EVENTS_DIR = COURIER_DIR / "events"
RESOURCE_INTEL_DIR = EVENTS_DIR / "resource-intelligence"
BENCHMARK_SESSION_FILE = RESOURCE_INTEL_DIR / "google_capacity_benchmark_session.json"


@dataclass
class JobRecord:
    task_id: str
    start_time: str
    end_time: str
    task_type: str  # REVENUE_ENABLING | REUSABLE_ASSET | RESEARCH | DETERMINISTIC_IMPL | VALIDATION
    model_or_google_product: str
    result: str  # PASS | FAIL | PARTIAL
    useful_output_count: int
    output_accepted: bool
    elapsed_seconds: float
    capacity_before: Union[float, str] = "UNKNOWN"
    capacity_after: Union[float, str] = "UNKNOWN"
    capacity_evidence: str = "UNVERIFIED"  # UNVERIFIED | PROVIDER_OBSERVED | UI_OBSERVED
    evidence_reference: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BenchmarkMetrics:
    tasks_attempted: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    useful_assets: int = 0
    accepted_assets: int = 0
    code_changes_accepted: int = 0
    tests_passed: int = 0
    research_jobs_accepted: int = 0
    revenue_assets_created: int = 0
    real_revenue_eur: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GoogleCapacityBenchmark:
    def __init__(
        self,
        account_alias: str = "google-account-pro-benchmark-01",
        plan: str = "GOOGLE_PRO",
        capacity_source: str = "UNKNOWN",
        observed_capacity: Optional[float] = None,
        session_file: Optional[Path] = None,
    ):
        self.session_file = session_file or BENCHMARK_SESSION_FILE
        self.account_alias = account_alias
        self.plan = plan
        self.account_count = 1
        self.spend_limit_eur = 0.0

        self.real_start_time = dt.datetime.now(dt.timezone.utc).isoformat()
        self.capacity_source = capacity_source  # PROVIDER_OBSERVED | UI_OBSERVED | UNKNOWN
        self.current_capacity = observed_capacity if observed_capacity is not None else "UNKNOWN"
        self.available_credits_info = "INCLUDED_IN_SUBSCRIPTION_0_EUR"

        self.state = "PROGRESSING"  # PROGRESSING | WAITING_RESOURCE | COMPLETED
        self.limit_type: Optional[str] = None  # PROVIDER_QUOTA_EXHAUSTION | FIVE_HOUR_LIMIT | SAFETY_GATE | NONE

        # Capacity curve timestamps (ISO or UNKNOWN)
        self.time_to_90_percent: Optional[str] = None
        self.time_to_75_percent: Optional[str] = None
        self.time_to_50_percent: Optional[str] = None
        self.time_to_25_percent: Optional[str] = None
        self.time_to_limit: Optional[str] = None

        self.jobs: List[JobRecord] = []
        self.metrics = BenchmarkMetrics()

        self._ensure_dir()
        if self.session_file.exists():
            self._load_session()
        else:
            self.save_session()

    def _load_session(self) -> None:
        try:
            data = json.loads(self.session_file.read_text(encoding="utf-8"))
            self.account_alias = data.get("account_alias", self.account_alias)
            self.plan = data.get("plan", self.plan)
            self.real_start_time = data.get("real_start_time", data.get("start_time", self.real_start_time))
            self.capacity_source = data.get("capacity_source", "UNKNOWN")
            self.current_capacity = data.get("current_capacity", "UNKNOWN")
            self.state = data.get("state", self.state)
            self.limit_type = data.get("limit_type", self.limit_type)
            thresholds = data.get("thresholds", {})
            self.time_to_90_percent = thresholds.get("time_to_90_percent") if thresholds.get("time_to_90_percent") != "UNKNOWN" else None
            self.time_to_75_percent = thresholds.get("time_to_75_percent") if thresholds.get("time_to_75_percent") != "UNKNOWN" else None
            self.time_to_50_percent = thresholds.get("time_to_50_percent") if thresholds.get("time_to_50_percent") != "UNKNOWN" else None
            self.time_to_25_percent = thresholds.get("time_to_25_percent") if thresholds.get("time_to_25_percent") != "UNKNOWN" else None
            self.time_to_limit = thresholds.get("time_to_limit") if thresholds.get("time_to_limit") != "NOT_REACHED" else None

            m = data.get("metrics", {})
            self.metrics = BenchmarkMetrics(
                tasks_attempted=m.get("tasks_attempted", 0),
                tasks_completed=m.get("tasks_completed", 0),
                tasks_failed=m.get("tasks_failed", 0),
                useful_assets=m.get("useful_assets", 0),
                accepted_assets=m.get("accepted_assets", 0),
                code_changes_accepted=m.get("code_changes_accepted", 0),
                tests_passed=m.get("tests_passed", 0),
                research_jobs_accepted=m.get("research_jobs_accepted", 0),
                revenue_assets_created=m.get("revenue_assets_created", 0),
                real_revenue_eur=m.get("real_revenue_eur", 0.0),
            )

            loaded_jobs = []
            for j in data.get("jobs", []):
                # Ensure all legacy or unverified records carry the explicit UNVERIFIED flag
                if "capacity_evidence" not in j:
                    j["capacity_evidence"] = "UNVERIFIED"
                loaded_jobs.append(JobRecord(**j))
            self.jobs = loaded_jobs
        except Exception as e:
            print(f"Warning: could not load existing session: {e}")
            self.save_session()

    def _ensure_dir(self) -> None:
        self.session_file.parent.mkdir(parents=True, exist_ok=True)

    def record_job(
        self,
        task_id: str,
        task_type: str,
        model_or_product: str,
        result: str,
        useful_output_count: int,
        output_accepted: bool,
        start_time: str,
        end_time: str,
        elapsed_seconds: float,
        evidence_reference: str = "",
        capacity_before: Union[float, str] = "UNKNOWN",
        capacity_after: Union[float, str] = "UNKNOWN",
        capacity_evidence: str = "UNVERIFIED",
        asset_type: Optional[str] = None,
        notes: str = "",
    ) -> JobRecord:
        """Record one real completed benchmark job with verifiable evidence reference."""
        record = JobRecord(
            task_id=task_id,
            start_time=start_time,
            end_time=end_time,
            task_type=task_type,
            model_or_google_product=model_or_product,
            result=result,
            useful_output_count=useful_output_count,
            output_accepted=output_accepted,
            elapsed_seconds=elapsed_seconds,
            capacity_before=capacity_before,
            capacity_after=capacity_after,
            capacity_evidence=capacity_evidence,
            evidence_reference=evidence_reference,
            notes=notes,
        )
        self.jobs.append(record)

        self.metrics.tasks_attempted += 1
        if result == "PASS":
            self.metrics.tasks_completed += 1
            if output_accepted:
                self.metrics.accepted_assets += useful_output_count
                if asset_type == "CODE":
                    self.metrics.code_changes_accepted += useful_output_count
                elif asset_type == "TEST":
                    self.metrics.tests_passed += useful_output_count
                elif asset_type == "RESEARCH":
                    self.metrics.research_jobs_accepted += useful_output_count
                elif asset_type == "REVENUE_ASSET":
                    self.metrics.revenue_assets_created += useful_output_count
            self.metrics.useful_assets += useful_output_count
        else:
            self.metrics.tasks_failed += 1

        self.save_session()
        return record

    def record_provider_limit(self, reset_time: Optional[str] = None, notes: str = "") -> None:
        """Record an actual provider limit event directly observed from Google."""
        now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
        self.state = "WAITING_RESOURCE"
        self.limit_type = "PROVIDER_QUOTA_EXHAUSTION"
        self.time_to_limit = now_iso
        self.save_session()

    def calculate_efficiency_metrics(self) -> Dict[str, Any]:
        """Calculates real useful output rates and elapsed wall-clock time."""
        now = dt.datetime.now(dt.timezone.utc)
        try:
            start_dt = dt.datetime.fromisoformat(self.real_start_time.replace("Z", "+00:00"))
            elapsed_hours = max((now - start_dt).total_seconds() / 3600.0, 0.0001)
        except Exception:
            elapsed_hours = 0.0001

        useful_output_per_hour = self.metrics.useful_assets / elapsed_hours
        accepted_output_per_hour = self.metrics.accepted_assets / elapsed_hours

        failure_rate = (
            self.metrics.tasks_failed / self.metrics.tasks_attempted
            if self.metrics.tasks_attempted > 0
            else 0.0
        )

        projected_24h_useful = accepted_output_per_hour * 24.0

        return {
            "elapsed_hours": round(elapsed_hours, 4),
            "capacity_source": self.capacity_source,
            "current_capacity": self.current_capacity,
            "useful_output_per_hour": round(useful_output_per_hour, 2),
            "accepted_output_per_hour": round(accepted_output_per_hour, 2),
            "failure_rate": round(failure_rate, 4),
            "projected_24h_useful_output": round(projected_24h_useful, 1),
            "account_expansion_candidate": "YES" if accepted_output_per_hour >= 2.0 and failure_rate < 0.1 else "NO",
        }

    def save_session(self) -> Path:
        efficiency = self.calculate_efficiency_metrics()
        data = {
            "benchmark_name": "GOOGLE_CAPACITY_BENCHMARK_1_ACCOUNT_24H",
            "account_alias": self.account_alias,
            "plan": self.plan,
            "account_count": self.account_count,
            "spend_limit_eur": self.spend_limit_eur,
            "real_start_time": self.real_start_time,
            "capacity_source": self.capacity_source,
            "current_capacity": self.current_capacity,
            "available_credits": self.available_credits_info,
            "state": self.state,
            "limit_type": self.limit_type,
            "thresholds": {
                "time_to_90_percent": self.time_to_90_percent or "UNKNOWN",
                "time_to_75_percent": self.time_to_75_percent or "UNKNOWN",
                "time_to_50_percent": self.time_to_50_percent or "UNKNOWN",
                "time_to_25_percent": self.time_to_25_percent or "UNKNOWN",
                "time_to_limit": self.time_to_limit or "NOT_REACHED",
            },
            "metrics": self.metrics.to_dict(),
            "efficiency": efficiency,
            "jobs": [j.to_dict() for j in self.jobs],
        }
        self.session_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return self.session_file
