#!/usr/bin/env python3
"""Bounded Deterministic AI Academy Demonstration Pipeline.

Demonstrates the complete Academy cycle:
1. Discovery: Teacher discovers external finding and calculates novelty hash.
2. Deduplication: Teacher checks uniqueness against existing lessons.
3. Opportunity Handoff: If opportunity candidate, hands off to Idea Sync (Thought Curator).
4. Director Review: Director checks attendance and approves for test.
5. Evaluation Gate: Director evaluates baseline vs candidate metrics (Pass/Fail).
6. Adoption Gate: Director approves adoption after verified eval pass.
7. Context Sync: Update Steward generates new incremented context snapshot.
8. Agent Delivery: Bounded lesson package delivered to target agent and acknowledged.

Cost: 0.00 EUR | Model Calls: 0
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
PROJECT_MEMORY_DIR = Path("/Users/user/Downloads/2026-project-memory")

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from run_academy import AcademyTeacher, AcademyDirector
from run_context_sync import UpdateSteward


_LITERAL_RUNTIMES = (12.5, 6.8)


def _is_number(value) -> bool:
    return type(value) in (int, float)


def _read_measurement(path: str | None) -> dict | None:
    """Read a measurement twice. Literals and unreadable files are not a result."""
    if not path:
        return None
    file_path = Path(path)
    if not file_path.is_file():
        return None
    try:
        first = json.loads(file_path.read_text(encoding="utf-8"))
        second = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if first != second or not isinstance(first, dict):
        return None
    baseline = first.get("baseline")
    candidate = first.get("candidate")
    if not isinstance(baseline, dict) or not isinstance(candidate, dict):
        return None
    if not _is_number(baseline.get("runtime_seconds")) or not _is_number(candidate.get("runtime_seconds")):
        return None
    if (baseline.get("runtime_seconds"), candidate.get("runtime_seconds")) == _LITERAL_RUNTIMES:
        return None
    if not _is_number(baseline.get("test_pass_rate")) or not _is_number(candidate.get("test_pass_rate")):
        return None
    if type(baseline.get("error_count")) is not int or type(candidate.get("error_count")) is not int:
        return None
    return first


def _matches_hundred_percent(record: dict) -> bool:
    baseline = record["baseline"]
    candidate = record["candidate"]
    return (
        baseline["test_pass_rate"] == 1.0
        and candidate["test_pass_rate"] == 1.0
        and candidate["error_count"] <= baseline["error_count"]
    )


def _not_measured(lesson_id: str) -> dict:
    print("Academy result was not measured. Not reporting a measured pass.")
    return {
        "status": "NOT_MEASURED",
        "exit_code": 1,
        "lesson_id": lesson_id,
        "eval_verdict": None,
        "context_version_before": None,
        "context_version_after": None,
        "measured_minutes_saved": None,
    }


def run_academy_demo(reset: bool = False, measurement_path: str | None = None) -> dict:
    print("=======================================================")
    print("🎓 STARTING AI ACADEMY DETERMINISTIC DEMO PIPELINE")
    print("   Teacher: Agentenlehrer | Director: Schuldirektor")
    print("=======================================================")

    teacher = AcademyTeacher(repo_dir=COURIER_DIR, memory_dir=PROJECT_MEMORY_DIR)
    director = AcademyDirector(repo_dir=COURIER_DIR, memory_dir=PROJECT_MEMORY_DIR)
    steward = UpdateSteward(repo_dir=COURIER_DIR, memory_dir=PROJECT_MEMORY_DIR)

    # 1. Attendance Check
    print("\n[STAGE 1] DIRECTOR ATTENDANCE CHECK...")
    director.check_attendance()

    # 2. External Finding & Lesson Proposal
    print("\n[STAGE 2] TEACHER DISCOVERING NEW EXTERNAL FINDING...")
    lesson = teacher.propose_lesson(
        topic="PROMPT_CACHING_OPTIMIZATION",
        title=f"Zero-Latency Static Prompt Caching Protocol {uuid.uuid4().hex[:6]}",
        summary="Optimizes repetitive context prefixes to reduce token latency by 45% and eliminate redundant parsing.",
        source="OpenAI / Google Anthropic Agent Architecture Patterns 2026",
        source_type="OFFICIAL_DOCS",
        affected_agents=["antigravity", "codex"],
        affected_workflows=["Autonomous Operations Loop", "Chief Review Relay"],
        current_method="Full prompt envelope reconstruction on each turn",
        proposed_method="Deterministic immutable system prompt prefix caching",
        expected_benefit="45% faster turn response time and 0 redundant token reprocessing",
        expected_time_saving="45% latency reduction",
        expected_cost_saving="Zero extra overhead",
        expected_quality_gain="Deterministic cache hits",
        risk="LOW",
        confidence=0.98,
        evidence="Standardized header prefix caching benchmarked across local test suites",
        lesson_type="PROCESS_IMPROVEMENT",
    )
    lesson_id = lesson["lesson_id"]
    print(f"   -> Lesson Proposal ID: {lesson_id} (Hash: {lesson['novelty_hash'][:12]})")

    # 3. Director Review
    print("\n[STAGE 3] DIRECTOR REVIEW & TEST GATE...")
    reviewed = director.review_lesson(lesson_id)
    assert reviewed["status"] == "APPROVED_FOR_TEST"
    print(f"   -> Status: {reviewed['status']} (Director State: TEST REQUIRED)")

    # 4. Evaluation uses a measurement file. In-source literals are not a result.
    print("\n[STAGE 4] EVALUATION LOOP (BASELINE vs CANDIDATE)...")
    measured = _read_measurement(measurement_path)
    if measured is None or not _matches_hundred_percent(measured):
        return _not_measured(lesson_id)
    baseline = measured["baseline"]
    candidate = measured["candidate"]
    eval_record = director.evaluate_lesson(lesson_id, baseline, candidate)
    reread = _read_measurement(measurement_path)
    if reread != measured or eval_record.get("verdict") != "PASS" or not _matches_hundred_percent(reread):
        print("Measured result does not match the pass claim. Not reporting success.")
        return {
            "status": "NOT_MEASURED",
            "exit_code": 1,
            "lesson_id": lesson_id,
            "eval_verdict": eval_record.get("verdict"),
            "context_version_before": None,
            "context_version_after": None,
            "measured_minutes_saved": None,
        }
    print(f"   -> Eval Verdict: {eval_record['verdict']} (Time saved: {eval_record['metrics']['measured_minutes_saved']} min)")

    # 5. Adoption Gate
    print("\n[STAGE 5] DIRECTOR ADOPTION GATE & UPDATE STEWARD CONTEXT REFRESH...")
    snap_before = steward.get_latest_snapshot()
    v_before = snap_before.get("context_version", 1) if snap_before else 1

    adoption = director.approve_adoption(lesson_id)
    snap_after = steward.get_latest_snapshot()
    v_after = snap_after.get("context_version", 1) if snap_after else 1
    print(f"   -> Adoption Approved: {adoption['adoption_id']}")
    print(f"   -> Context Snapshot Refreshed: v{v_before} -> v{v_after} (Hash: {snap_after.get('snapshot_hash', '')[:12]})")

    # 6. Bounded Agent Teaching & Acknowledgement
    print("\n[STAGE 6] DELIVERING BOUNDED LESSON TO AGENT...")
    delivery = teacher.queue_or_deliver_lesson(lesson_id, target_agent="agent-antigravity-bridge")
    print(f"   -> Delivery Package: {delivery['delivery_id']} (Status: {delivery['status']})")

    ack = director.record_worker_acknowledgement(
        worker_agent_id="agent-antigravity-bridge",
        lesson_id=lesson_id,
        context_version=v_after,
    )
    print(f"   -> Worker Acknowledgement: {ack['adoption_status']} for lesson {lesson_id}")

    print("\n=======================================================")
    print("✅ AI ACADEMY DEMO COMPLETED SUCCESSFULLY: 100% PASS")
    print("=======================================================")

    return {
        "status": "COMPLETED",
        "exit_code": 0,
        "lesson_id": lesson_id,
        "eval_verdict": eval_record["verdict"],
        "context_version_before": v_before,
        "context_version_after": v_after,
        "measured_minutes_saved": eval_record["metrics"]["measured_minutes_saved"],
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="AI Academy Demo Runner")
    parser.add_argument("--reset", action="store_true", help="Reset academy test data before running")
    parser.add_argument("--measurement", default=None, help="Path to a measured baseline and candidate result")
    args = parser.parse_args(argv)
    result = run_academy_demo(reset=args.reset, measurement_path=args.measurement)
    sys.exit(result.get("exit_code", 1))


if __name__ == "__main__":
    main()
