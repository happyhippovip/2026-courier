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


def run_academy_demo(reset: bool = False) -> dict:
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

    # 4. Evaluation Loop
    print("\n[STAGE 4] EVALUATION LOOP (BASELINE vs CANDIDATE)...")
    baseline = {
        "method": "Full prompt reconstruction",
        "runtime_seconds": 12.5,
        "error_count": 0,
        "test_pass_rate": 1.0,
    }
    candidate = {
        "method": "Prefix cached prompt protocol",
        "runtime_seconds": 6.8,
        "error_count": 0,
        "test_pass_rate": 1.0,
    }
    eval_record = director.evaluate_lesson(lesson_id, baseline, candidate)
    assert eval_record["verdict"] == "PASS"
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
        "lesson_id": lesson_id,
        "eval_verdict": eval_record["verdict"],
        "context_version_before": v_before,
        "context_version_after": v_after,
        "measured_minutes_saved": eval_record["metrics"]["measured_minutes_saved"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Academy Demo Runner")
    parser.add_argument("--reset", action="store_true", help="Reset academy test data before running")
    args = parser.parse_args()

    run_academy_demo(reset=args.reset)
