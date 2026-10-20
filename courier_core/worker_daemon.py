"""Unified Worker Daemon Runtime with Resilience Wiring.

Integrates pre-flight resource checks, zero-cost authorization gating,
execution tracing, cryptographic receipt signing on success, and automated
crash report harvesting + dead-letter queue isolation on failure.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from courier_core.crash_harvester import CrashHarvester, CrashReport, create_diagnostic_bundle
from courier_core.dead_letter_queue import DeadLetterQueue, DLQEntry
from courier_core.provider_cost_guard import evaluate_cost_gate, CostGateVerdict
from courier_core.receipt_signer import ReceiptSigner, SignedReceipt
from courier_core.resource_watchdog import evaluate_resource_health


@dataclass
class TaskCycleResult:
    """Detailed outcome of a single task execution cycle."""

    status: str  # "SUCCESS" | "FAILED" | "RESOURCE_PRESSURE" | "COOLDOWN_ACTIVE" | "COST_GATE_BLOCKED"
    item_id: str
    signed_receipt: SignedReceipt | None = None
    crash_report: CrashReport | None = None
    dlq_entry: DLQEntry | None = None
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "item_id": self.item_id,
            "signed_receipt": self.signed_receipt.to_dict() if self.signed_receipt else None,
            "crash_report": self.crash_report.to_dict() if self.crash_report else None,
            "dlq_entry": self.dlq_entry.to_dict() if self.dlq_entry else None,
            "error_message": self.error_message,
        }


class WorkerDaemon:
    """Daemon harness managing execution, security guards, and failure containment."""

    def __init__(
        self,
        worker_id: str = "windows-titan",
        secret_key: str = "dev-secret-token",
        work_dir: str = ".",
        outbox_dir: str = "run/outbox",
        crash_dir: str = "run/crashes",
        dlq_file: str = "run/dlq.json",
        cost_limit_eur: float = 0.0,
    ):
        self.worker_id = worker_id
        self.secret_key = secret_key
        self.work_dir = Path(work_dir)
        self.outbox_dir = Path(outbox_dir)
        self.crash_dir = Path(crash_dir)
        self.cost_limit_eur = cost_limit_eur

        self.signer = ReceiptSigner(secret_key=self.secret_key)
        self.harvester = CrashHarvester(work_dir=str(self.work_dir))
        self.dlq = DeadLetterQueue(dlq_path=dlq_file)

    def execute_task_cycle(
        self,
        item_id: str,
        handler_fn: Callable[[], dict[str, Any] | Any],
        cost_spec: dict[str, Any] | None = None,
    ) -> TaskCycleResult:
        # 1. Pre-flight Resource Check
        report = evaluate_resource_health(home_path=self.work_dir)
        if report.state == "PRESSURED":
            return TaskCycleResult(
                status="RESOURCE_PRESSURE",
                item_id=item_id,
                error_message=";".join(report.pressure_reasons) or "RESOURCE_PRESSURE",
            )
        if report.state == "COOLDOWN":
            return TaskCycleResult(
                status="COOLDOWN_ACTIVE",
                item_id=item_id,
                error_message="Cooldown active from recent resource pressure",
            )

        # 2. Pre-flight Cost Authorization Check
        if cost_spec is None:
            return TaskCycleResult(
                status="COST_GATE_BLOCKED",
                item_id=item_id,
                error_message="UNKNOWN_COST_BLOCKED",
            )
        cost_verdict = evaluate_cost_gate(cost_spec, autonomous_limit_eur=self.cost_limit_eur)
        if not cost_verdict.allowed:
            return TaskCycleResult(
                status="COST_GATE_BLOCKED",
                item_id=item_id,
                error_message=cost_verdict.reason,
            )

        # 3. Task Execution
        try:
            handler_result = handler_fn()
            if isinstance(handler_result, dict):
                reported_status = str(handler_result.get("status", "DONE")).strip().upper()
                if reported_status in ("FAILED", "FAIL", "ERROR", "BLOCKED", "REJECTED", "ABORTED"):
                    err_detail = (
                        handler_result.get("error")
                        or handler_result.get("reason")
                        or f"Handler returned failure status: {reported_status}"
                    )
                    raise RuntimeError(str(err_detail))

            payload = {
                "event_id": f"evt-{uuid.uuid4().hex[:8]}",
                "item_id": item_id,
                "worker_id": self.worker_id,
                "status": "DONE",
            }
            if isinstance(handler_result, dict):
                payload.update(handler_result)
            elif handler_result is not None:
                payload["output"] = str(handler_result)

            # Cryptographic receipt signing
            signed = self.signer.sign(payload)

            # Persist to outbox
            self.outbox_dir.mkdir(parents=True, exist_ok=True)
            receipt_file = self.outbox_dir / f"receipt_{item_id}.json"
            receipt_file.write_text(json.dumps(signed.to_dict(), indent=2), encoding="utf-8")

            return TaskCycleResult(
                status="SUCCESS",
                item_id=item_id,
                signed_receipt=signed,
            )

        except Exception as exc:
            # 4. Crash Extraction & Secret Scrubbing
            raw_trace = traceback.format_exc()
            report = self.harvester.harvest_from_text(
                f"{str(exc)}\n{raw_trace}",
                item_id=item_id,
            )
            create_diagnostic_bundle(report, str(self.crash_dir))

            # 5. Dead-Letter Queue Recording
            dlq_entry = self.dlq.record_failure(
                item_id=item_id,
                error_reason=report.error_message,
                attempts=1,
            )

            return TaskCycleResult(
                status="FAILED",
                item_id=item_id,
                crash_report=report,
                dlq_entry=dlq_entry,
                error_message=report.error_message,
            )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Unified Worker Daemon.")
    parser.add_argument("--item", required=True, help="Work item ID to execute")
    parser.add_argument("--worker-id", default="windows-titan", help="Worker identifier")
    parser.add_argument("--key", default="dev-secret-token", help="Cryptographic HMAC secret key")
    parser.add_argument("--outbox", default="run/outbox", help="Directory for signed receipts")
    parser.add_argument("--crashes", default="run/crashes", help="Directory for crash dumps")
    parser.add_argument("--dlq-file", default="run/dlq.json", help="DLQ state file")
    parser.add_argument("--cost-spec", default=None, help="JSON string or path for provider cost spec")
    parser.add_argument("--cost-estimate", type=float, default=None, help="Explicit cost estimate in EUR")
    parser.add_argument("--provider", default="local_titan", help="Provider name")
    parser.add_argument("--model", default="v30", help="Model name")
    parser.add_argument("--mock-success", action="store_true", help="Simulate successful execution")
    parser.add_argument("--mock-fail", action="store_true", help="Simulate failing execution")

    args = parser.parse_args(argv)

    daemon = WorkerDaemon(
        worker_id=args.worker_id,
        secret_key=args.key,
        outbox_dir=args.outbox,
        crash_dir=args.crashes,
        dlq_file=args.dlq_file,
    )

    cost_spec = None
    if args.cost_spec:
        try:
            if os.path.exists(args.cost_spec):
                with open(args.cost_spec, "r", encoding="utf-8") as f:
                    cost_spec = json.load(f)
            else:
                cost_spec = json.loads(args.cost_spec)
        except Exception:
            cost_spec = None
    elif args.cost_estimate is not None:
        cost_spec = {
            "provider": args.provider,
            "model": args.model,
            "cost_estimate_eur": args.cost_estimate,
        }
    elif args.mock_success or args.mock_fail:
        cost_spec = {
            "provider": args.provider,
            "model": args.model,
            "cost_estimate_eur": 0.0,
        }

    if args.mock_fail:
        def handler():
            raise RuntimeError("Mock failure requested by CLI flag")
    else:
        def handler():
            return {"status": "DONE", "result": "Mock execution completed"}

    res = daemon.execute_task_cycle(item_id=args.item, handler_fn=handler, cost_spec=cost_spec)
    print(json.dumps(res.to_dict()))
    return 0 if res.status == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
