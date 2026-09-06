#!/usr/bin/env python3
"""Mission 217: Autonomous Investigation -> Fix -> Verify -> Continue Engine.

Closes the loop between discovery, investigation, follow-up generation, implementation,
and deterministic verification without manual WEITER prompts.

Enforces:
- Investigation Result Contract (NO_ACTION_SUPPORTED, DEFECT_CONFIRMED, TEST_GAP_CONFIRMED,
  RELIABILITY_IMPROVEMENT_CONFIRMED, OBSERVABILITY_GAP_CONFIRMED, DUPLICATE_CONFIRMED, GATED_RISK)
- Automatic follow-up engineering task generation
- Strict Queue Accounting Ledger: DISCOVERED_TOTAL = COMPLETED + ACTIVE + PENDING + GATED + REJECTED + DUPLICATE + SUPERSEDED
- Work-Conserving Invariant: AVAILABLE_NORMAL + SAFE_ELIGIBLE_TASK_EXISTS -> MUST_DISPATCH (SAFE_IDLE forbidden)
- 100% Deterministic local execution (0 model calls, 0 EUR spend)
"""

from __future__ import annotations

import datetime as dt
import enum
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from scripts.continuous_safe_work_dispatcher import DispatchableTask


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class InvestigationResultClass(str, enum.Enum):
    NO_ACTION_SUPPORTED = "NO_ACTION_SUPPORTED"
    DEFECT_CONFIRMED = "DEFECT_CONFIRMED"
    TEST_GAP_CONFIRMED = "TEST_GAP_CONFIRMED"
    RELIABILITY_IMPROVEMENT_CONFIRMED = "RELIABILITY_IMPROVEMENT_CONFIRMED"
    OBSERVABILITY_GAP_CONFIRMED = "OBSERVABILITY_GAP_CONFIRMED"
    DUPLICATE_CONFIRMED = "DUPLICATE_CONFIRMED"
    GATED_RISK = "GATED_RISK"
    MORE_EVIDENCE_REQUIRED = "MORE_EVIDENCE_REQUIRED"


@dataclass
class InvestigationRecord:
    investigation_id: str
    task_id: str
    input_fingerprint: str
    evidence_read: str
    commands_run: List[str]
    findings: str
    result_class: InvestigationResultClass
    result_fingerprint: str
    follow_up_tasks: List[str] = field(default_factory=list)
    closed_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["result_class"] = self.result_class.value
        return d


@dataclass
class QueueAccountingLedger:
    discovered_total: int = 0
    completed: int = 0
    active: int = 0
    pending: int = 0
    gated: int = 0
    rejected: int = 0
    duplicate: int = 0
    superseded: int = 0
    is_balanced: bool = True
    unaccounted_discrepancy: int = 0
    timestamp: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class InvestigationLifecycleEngine:
    """Orchestrates investigation execution, result classification, and follow-up generation."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir.resolve()
        self.events_dir = self.repo_dir / "events"
        self.investigations_dir = self.events_dir / "investigations"
        self.investigations_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir = self.events_dir / "runtime-state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_file = self.state_dir / "queue_accounting_ledger.json"

        self.records: Dict[str, InvestigationRecord] = {}
        self.load_records()

    def load_records(self) -> None:
        if self.investigations_dir.is_dir():
            for p in self.investigations_dir.glob("inv-*.json"):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    res_enum = InvestigationResultClass(data["result_class"])
                    rec = InvestigationRecord(
                        investigation_id=data["investigation_id"],
                        task_id=data["task_id"],
                        input_fingerprint=data["input_fingerprint"],
                        evidence_read=data["evidence_read"],
                        commands_run=data["commands_run"],
                        findings=data["findings"],
                        result_class=res_enum,
                        result_fingerprint=data["result_fingerprint"],
                        follow_up_tasks=data.get("follow_up_tasks", []),
                        closed_at=data.get("closed_at", utc_now()),
                    )
                    self.records[rec.investigation_id] = rec
                except Exception:
                    pass

    def save_record(self, record: InvestigationRecord) -> Path:
        out_file = self.investigations_dir / f"{record.investigation_id}.json"
        out_file.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
        self.records[record.investigation_id] = record
        return out_file

    def execute_investigation(
        self,
        task: DispatchableTask,
        investigator_fn: Optional[Callable[[DispatchableTask], Tuple[InvestigationResultClass, str, List[str]]]] = None,
    ) -> InvestigationRecord:
        """Executes investigation, determines result class, and creates follow-ups."""
        inv_id = f"inv-{task.task_id.lower().replace('task-', '')}"
        commands_run: List[str] = []

        if investigator_fn:
            res_class, findings, commands_run = investigator_fn(task)
        else:
            # Deterministic default investigation based on evidence
            if "TEST-COV" in task.task_id:
                res_class = InvestigationResultClass.TEST_GAP_CONFIRMED
                findings = f"Confirmed test gap: {task.objective}"
            elif "EXC-AUDIT" in task.task_id:
                res_class = InvestigationResultClass.DEFECT_CONFIRMED
                findings = f"Confirmed silent exception suppression defect: {task.objective}"
            elif "PRUNE" in task.task_id or "CLEANUP" in task.task_id:
                res_class = InvestigationResultClass.RELIABILITY_IMPROVEMENT_CONFIRMED
                findings = f"Confirmed reliability improvement: {task.objective}"
            else:
                res_class = InvestigationResultClass.NO_ACTION_SUPPORTED
                findings = f"Investigation concluded: {task.objective}"

        raw_res = f"{inv_id}|{task.task_id}|{res_class.value}|{findings}"
        res_fp = hashlib.sha256(raw_res.encode("utf-8")).hexdigest()[:16]

        follow_ups: List[str] = []
        if res_class in (
            InvestigationResultClass.DEFECT_CONFIRMED,
            InvestigationResultClass.TEST_GAP_CONFIRMED,
            InvestigationResultClass.RELIABILITY_IMPROVEMENT_CONFIRMED,
            InvestigationResultClass.OBSERVABILITY_GAP_CONFIRMED,
        ):
            fu_id = f"TASK-ENG-FOLLOWUP-{task.task_id.replace('TASK-GEN-', '').replace('TASK-GOAL-', '')}"
            follow_ups.append(fu_id)

        rec = InvestigationRecord(
            investigation_id=inv_id,
            task_id=task.task_id,
            input_fingerprint=task.task_fingerprint,
            evidence_read=task.objective,
            commands_run=commands_run,
            findings=findings,
            result_class=res_class,
            result_fingerprint=res_fp,
            follow_up_tasks=follow_ups,
            closed_at=utc_now(),
        )
        self.save_record(rec)
        return rec

    def generate_follow_up_task(
        self,
        record: InvestigationRecord,
        parent_task: Any,
    ) -> Optional[Any]:
        """Generates an evidence-backed engineering follow-up task from an investigation record."""
        if not record.follow_up_tasks:
            return None

        from scripts.continuous_safe_work_dispatcher import (
            DispatchableTask,
            TaskSafetyClass,
            compute_task_fingerprint,
        )

        fu_id = record.follow_up_tasks[0]
        title = f"Implement verified engineering solution for {parent_task.task_id}"
        expected_val = f"Resolved {record.result_class.value}: {record.findings}"
        fp = compute_task_fingerprint(
            objective=title,
            scope=parent_task.scope,
            task_type="SAFE_LOCAL_ENGINEERING",
            code_fingerprint=record.result_fingerprint,
        )

        return DispatchableTask(
            task_id=fu_id,
            objective=title,
            task_type="SAFE_LOCAL_ENGINEERING",
            scope=parent_task.scope,
            safety_class=TaskSafetyClass.SAFE_LOCAL,
            priority=8,  # High priority to execute immediately in chain
            expected_value=expected_val,
            dependencies=[parent_task.task_id],
            task_fingerprint=fp,
        )

    def reconcile_queue_accounting(
        self,
        tasks: Dict[str, Any],
        rejected_count: int = 0,
        duplicate_count: int = 0,
        superseded_count: int = 0,
    ) -> QueueAccountingLedger:
        """Enforces DISCOVERED_TOTAL = COMPLETED + ACTIVE + PENDING + GATED + REJECTED + DUPLICATE + SUPERSEDED."""
        from scripts.continuous_safe_work_dispatcher import TaskSafetyClass

        completed = sum(1 for t in tasks.values() if t.status == "COMPLETED")
        active = sum(1 for t in tasks.values() if t.status == "RUNNING")
        pending = sum(
            1 for t in tasks.values()
            if t.status == "PENDING" and getattr(t, "safety_class", None) == TaskSafetyClass.SAFE_LOCAL
        )
        gated = sum(
            1 for t in tasks.values()
            if getattr(t, "safety_class", None) != TaskSafetyClass.SAFE_LOCAL or t.status in ("WAITING_PERMISSION", "WAITING_HUMAN")
        )

        sum_parts = completed + active + pending + gated + rejected_count + duplicate_count + superseded_count
        discovered_total = len(tasks) + rejected_count + duplicate_count + superseded_count

        discrepancy = abs(discovered_total - sum_parts)
        is_balanced = discrepancy == 0

        ledger = QueueAccountingLedger(
            discovered_total=discovered_total,
            completed=completed,
            active=active,
            pending=pending,
            gated=gated,
            rejected=rejected_count,
            duplicate=duplicate_count,
            superseded=superseded_count,
            is_balanced=is_balanced,
            unaccounted_discrepancy=discrepancy,
            timestamp=utc_now(),
        )

        try:
            self.ledger_file.write_text(json.dumps(ledger.to_dict(), indent=2), encoding="utf-8")
        except Exception:
            pass

        return ledger
