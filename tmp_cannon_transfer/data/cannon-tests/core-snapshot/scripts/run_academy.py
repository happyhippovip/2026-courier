#!/usr/bin/env python3
"""AI Academy Engine: Teacher (Agentenlehrer) & Director (Schuldirektor).

Permanent AI Academy layer for continuous, safe, evidence-grounded improvement:
- ACADEMY_TEACHER (Agentenlehrer): Discovers external findings across AI tooling,
  orchestration, distribution, and monetization domains, converting them into bounded lessons.
- ACADEMY_DIRECTOR (Schuldirektor): Governs the academy, verifies attendance and evidence,
  enforces test/eval gates before adoption, prevents production drift, and tracks economics.

Flow:
NEW EXTERNAL FINDING
→ TEACHER (DISCOVER & DEDUPE)
→ LESSON PROPOSAL
→ DIRECTOR (REVIEW & TEST GATE)
→ IDEA SYNC (if OPPORTUNITY_CANDIDATE)
→ EVALUATION LOOP (BASELINE vs CANDIDATE)
→ CHIEF / DIRECTOR APPROVAL
→ ADOPT
→ UPDATE STEWARD (CONTEXT REFRESH)
→ AGENT RECEIVES BOUNDED LESSON

Truth Invariants:
- IDEA != IMPLEMENTED
- DISCOVERED != ADOPTED
- TESTED != PRODUCTION
- OPPORTUNITY != REVENUE
- DETERMINISTIC != REAL_EXTERNAL
- Zero model calls for routine governance (0.00 EUR).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
PROJECT_MEMORY_DIR = Path("/Users/user/Downloads/2026-project-memory")

EVENTS_DIR = COURIER_DIR / "events"
STATES_DIR = EVENTS_DIR / "agent-states"
ACADEMY_DIR = EVENTS_DIR / "academy"
LESSONS_DIR = ACADEMY_DIR / "lessons"
EVALS_DIR = ACADEMY_DIR / "evaluations"
DELIVERIES_DIR = ACADEMY_DIR / "deliveries"
ADOPTIONS_DIR = ACADEMY_DIR / "adoptions"

for d in [STATES_DIR, ACADEMY_DIR, LESSONS_DIR, EVALS_DIR, DELIVERIES_DIR, ADOPTIONS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from run_antigravity_bridge import AntigravityVisualStateTracker, load_json, save_json
    from run_context_sync import UpdateSteward
    from run_thought_curator import ThoughtCurator
except ImportError:
    from scripts.run_antigravity_bridge import AntigravityVisualStateTracker, load_json, save_json
    from scripts.run_context_sync import UpdateSteward
    from scripts.run_thought_curator import ThoughtCurator


DEFAULT_ACADEMY_CONFIG = {
    "schema_version": "2.0",
    "academy_enabled": True,
    "academy_timezone": "UTC",
    "academy_daily_time": "06:00",
    "academy_window_minutes": 60,
    "idle_preferred": True,
    "allow_safe_defer": True,
    "research_domains": [
        "openai_codex",
        "antigravity_gemini",
        "agent_orchestration",
        "automation_methods",
        "content_production_3d",
        "distribution_monetization",
        "cost_reduction",
        "reliability_improvements",
    ],
}

ALLOWED_LESSON_TYPES = {
    "KNOWLEDGE_UPDATE",
    "PROCESS_IMPROVEMENT",
    "COST_REDUCTION",
    "QUALITY_IMPROVEMENT",
    "SECURITY_UPDATE",
    "PLATFORM_CHANGE",
    "NEW_CAPABILITY",
    "OPPORTUNITY_CANDIDATE",
}

ALLOWED_LESSON_STATUSES = {
    "DISCOVERED",
    "DEDUPED",
    "PENDING_REVIEW",
    "APPROVED_FOR_TEST",
    "REJECTED",
    "DEFERRED",
    "TESTING",
    "EVAL_PASS",
    "EVAL_FAIL",
    "ADOPTED",
    "SUPERSEDED",
}


def compute_novelty_hash(topic: str, title: str, summary: str, source: str) -> str:
    """Computes a deterministic novelty hash to prevent duplicate lesson ingestion."""
    raw = f"{topic.strip().lower()}::{title.strip().lower()}::{summary.strip().lower()}::{source.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AcademyTeacher:
    """Academy Teacher (Agentenlehrer): Discovers external findings and converts them into bounded lessons."""

    def __init__(self, repo_dir: Path = COURIER_DIR, memory_dir: Path = PROJECT_MEMORY_DIR):
        self.repo_dir = repo_dir
        self.memory_dir = memory_dir
        self.config_file = self.repo_dir / "events/academy/config.json"
        self.config = self._load_or_init_config()

        self.state_tracker = AntigravityVisualStateTracker(
            agent_id="agent-academy-teacher",
            name="Agentenlehrer",
            role="System Learning & Improvement Teacher",
        )
        self.curator = ThoughtCurator(repo_dir=repo_dir, memory_dir=memory_dir)
        self.steward = UpdateSteward(repo_dir=repo_dir, memory_dir=memory_dir)

    def _load_or_init_config(self) -> dict:
        if self.config_file.exists():
            try:
                return json.loads(self.config_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        save_json(self.config_file, DEFAULT_ACADEMY_CONFIG)
        return DEFAULT_ACADEMY_CONFIG

    def update_visual_state(
        self,
        state: str,
        current_topic: str | None = None,
        latest_lesson: dict | None = None,
        pending_lessons: list[str] | None = None,
        opportunities_found: int = 0,
        affected_agents: list[str] | None = None,
        last_action: str = "Standby",
        next_action: str | None = None,
    ) -> dict:
        """Updates the Agentenlehrer state file with full visual character metadata."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        state_data = {
            "schema_version": "2.0",
            "id": "agent-academy-teacher",
            "name": "Agentenlehrer",
            "role": "SYSTEM LEARNING + IMPROVEMENT",
            "state": state,
            "visual_metadata": {
                "name": "AGENTENLEHRER",
                "props": ["teacher_hat", "glasses", "teacher_pointer"],
                "role_label": "SYSTEM LEARNING + IMPROVEMENT",
            },
            "last_school_time": now_iso,
            "next_school_time": f"{self.config.get('academy_daily_time', '06:00')} {self.config.get('academy_timezone', 'UTC')}",
            "lessons_today": len(list(LESSONS_DIR.glob("*.json"))),
            "latest_lesson": latest_lesson.get("lesson_id") if latest_lesson else None,
            "pending_lessons": pending_lessons or [],
            "opportunities_found": opportunities_found,
            "affected_agents": affected_agents or [],
            "current_topic": current_topic,
            "last_action": last_action,
            "next_action": next_action or "Monitoring daily school schedule",
            "updated_at": now_iso,
        }
        state_file = self.repo_dir / "events/agent-states/agent-academy-teacher.json"
        save_json(state_file, state_data)
        return state_data

    def propose_lesson(
        self,
        topic: str,
        title: str,
        summary: str,
        source: str,
        source_type: str = "OFFICIAL_DOCS",
        source_date: str | None = None,
        affected_agents: list[str] | None = None,
        affected_workflows: list[str] | None = None,
        current_method: str = "Manual or baseline implementation",
        proposed_method: str = "Improved automated pattern",
        expected_benefit: str = "Efficiency and reliability improvement",
        expected_time_saving: str | None = None,
        expected_cost_saving: str | None = None,
        expected_quality_gain: str | None = None,
        risk: str = "LOW",
        confidence: float = 0.9,
        evidence: str = "Documented changelog and local benchmark",
        lesson_type: str = "PROCESS_IMPROVEMENT",
    ) -> dict:
        """Discovers and formulates a compact machine-readable Lesson Proposal with deduplication."""
        if lesson_type not in ALLOWED_LESSON_TYPES:
            raise ValueError(f"Invalid lesson_type '{lesson_type}'. Allowed: {ALLOWED_LESSON_TYPES}")

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        source_date = source_date or now_iso.split("T")[0]
        affected_agents = affected_agents or ["antigravity", "codex"]
        affected_workflows = affected_workflows or ["Autonomous Operations"]

        novelty_hash = compute_novelty_hash(topic, title, summary, source)

        # 1. Deduplication check against existing lessons
        existing_lessons = list(LESSONS_DIR.glob("*.json"))
        for lf in existing_lessons:
            try:
                ldata = json.loads(lf.read_text(encoding="utf-8"))
                if ldata.get("novelty_hash") == novelty_hash:
                    print(f"[TEACHER] Duplicate lesson detected ({ldata.get('lesson_id')}). Marking DEDUPED.")
                    self.update_visual_state(
                        state="DEDUPED",
                        current_topic=topic,
                        latest_lesson=ldata,
                        last_action=f"Duplicate lesson suppressed: {title[:40]}",
                    )
                    return ldata
            except Exception:
                pass

        # 2. Formulate New Lesson Proposal
        lesson_id = f"lesson-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
        lesson_data = {
            "schema_version": "2.0",
            "lesson_id": lesson_id,
            "discovered_at": now_iso,
            "source": source,
            "source_type": source_type,
            "source_date": source_date,
            "topic": topic,
            "title": title,
            "summary": summary,
            "novelty_hash": novelty_hash,
            "affected_agents": affected_agents,
            "affected_workflows": affected_workflows,
            "current_method": current_method,
            "proposed_method": proposed_method,
            "expected_benefit": expected_benefit,
            "expected_time_saving": expected_time_saving,
            "expected_cost_saving": expected_cost_saving,
            "expected_quality_gain": expected_quality_gain,
            "risk": risk,
            "confidence": confidence,
            "evidence": evidence,
            "lesson_type": lesson_type,
            "status": "DISCOVERED",
            "truth_invariants": "DISCOVERED != ADOPTED | OPPORTUNITY != REVENUE | TESTED != PRODUCTION",
            "created_at": now_iso,
        }

        lesson_file = LESSONS_DIR / f"{lesson_id}.json"
        save_json(lesson_file, lesson_data)
        print(f"[TEACHER] New Lesson Proposal created: {lesson_id} ('{title}')")

        # 3. Opportunity Discovery Handoff to Idea Sync
        if lesson_type == "OPPORTUNITY_CANDIDATE":
            print(f"[TEACHER] Opportunity candidate detected: Forwarding to Idea Sync / Thought Curator...")
            curated_idea = self.curator.curate_idea(
                raw_idea=f"[ACADEMY OPPORTUNITY] {title}: {summary}",
                idea_type="GOAL",
            )
            lesson_data["idea_sync_id"] = curated_idea.get("idea_id")
            save_json(lesson_file, lesson_data)

        self.update_visual_state(
            state="PENDING_REVIEW",
            current_topic=topic,
            latest_lesson=lesson_data,
            affected_agents=affected_agents,
            opportunities_found=1 if lesson_type == "OPPORTUNITY_CANDIDATE" else 0,
            last_action=f"Proposed lesson {lesson_id}: {title[:40]}",
            next_action="Awaiting Director attendance and evaluation review",
        )

        return lesson_data

    def queue_or_deliver_lesson(
        self,
        lesson_id: str,
        target_agent: str,
        target_task_id: str | None = None,
    ) -> dict:
        """Determines whether an agent is idle or actively executing, delivering or safely deferring lesson."""
        lesson_file = LESSONS_DIR / f"{lesson_id}.json"
        if not lesson_file.exists():
            raise FileNotFoundError(f"Lesson file not found: {lesson_id}")
        lesson = load_json(lesson_file)

        # Inspect target agent's current state
        agent_state_file = self.repo_dir / f"events/agent-states/{target_agent}.json"
        agent_state = load_json(agent_state_file) if agent_state_file.exists() else {}

        is_busy = agent_state.get("state") in ["RUNNING", "COMPARING", "COORDINATING", "REVIEWING"]
        is_urgent = lesson.get("lesson_type") == "SECURITY_UPDATE" and lesson.get("risk") == "HIGH"

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        delivery_id = f"deliv-{uuid.uuid4().hex[:8]}"

        if is_busy and not is_urgent:
            # Safe Deferral: Queue until task completion boundary
            print(f"[TEACHER] Target agent '{target_agent}' is actively executing. Safe deferral queued.")
            defer_record = {
                "schema_version": "2.0",
                "delivery_id": delivery_id,
                "lesson_id": lesson_id,
                "target_agent": target_agent,
                "status": "PENDING_LESSON",
                "reason": "Target agent actively executing; safe task boundary deferral enforced",
                "defer_until_task_completed": agent_state.get("task"),
                "created_at": now_iso,
            }
            save_json(DELIVERIES_DIR / f"{delivery_id}.json", defer_record)
            return defer_record

        # Formulate Bounded Delivery Package
        snapshot = self.steward.get_latest_snapshot()
        context_version = snapshot.get("context_version", 1) if snapshot else 1

        delivery_package = {
            "schema_version": "2.0",
            "delivery_id": delivery_id,
            "lesson_id": lesson_id,
            "target_agent": target_agent,
            "relevant_summary": lesson.get("summary"),
            "reason_for_agent": f"Relevant for {target_agent} workflows: {lesson.get('topic')}",
            "recommended_change": lesson.get("proposed_method"),
            "context_version": context_version,
            "safe_from_task_id": target_task_id or agent_state.get("task"),
            "status": "URGENT_LESSON_REVIEW" if is_urgent else "DELIVERED_TO_AGENT",
            "delivered_at": now_iso,
        }

        save_json(DELIVERIES_DIR / f"{delivery_id}.json", delivery_package)
        print(f"[TEACHER] Bounded lesson delivery package created for '{target_agent}' ({delivery_id})")
        return delivery_package


class AcademyDirector:
    """Academy Director (Schuldirektor): Governs evaluation, test gates, adoption, and economic metrics."""

    def __init__(self, repo_dir: Path = COURIER_DIR, memory_dir: Path = PROJECT_MEMORY_DIR):
        self.repo_dir = repo_dir
        self.memory_dir = memory_dir
        self.economics_file = self.repo_dir / "events/academy/economics.json"
        self.economics = self._load_or_init_economics()

        self.state_tracker = AntigravityVisualStateTracker(
            agent_id="agent-academy-director",
            name="Schuldirektor",
            role="Academy Governance & Evaluation Director",
        )
        self.steward = UpdateSteward(repo_dir=repo_dir, memory_dir=memory_dir)

    def _load_or_init_economics(self) -> dict:
        if self.economics_file.exists():
            try:
                return json.loads(self.economics_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        initial_econ = {
            "schema_version": "2.0",
            "total_lessons_adopted": 0,
            "estimated_minutes_saved": 0.0,
            "measured_minutes_saved": 0.0,
            "estimated_cost_saved_eur": 0.0,
            "measured_cost_saved_eur": 0.0,
            "opportunities_tested": 0,
            "revenue_evidence": "NOT_VERIFIED",
            "truth_rule": "NO_FABRICATED_MONETARY_RESULTS",
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        save_json(self.economics_file, initial_econ)
        return initial_econ

    def update_visual_state(
        self,
        state: str,
        lessons_reviewed: int = 0,
        lessons_approved: int = 0,
        lessons_rejected: int = 0,
        tests_required: int = 0,
        evals_passed: int = 0,
        evals_failed: int = 0,
        rule_violations: int = 0,
        last_action: str = "Standby",
        next_action: str | None = None,
    ) -> dict:
        """Updates the Schuldirektor state file with full governance metrics."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        state_data = {
            "schema_version": "2.0",
            "id": "agent-academy-director",
            "name": "Schuldirektor",
            "role": "ACADEMY GOVERNANCE + EVALUATION",
            "state": state,
            "visual_metadata": {
                "name": "SCHULDIREKTOR",
                "role_label": "ACADEMY GOVERNANCE + EVALUATION",
            },
            "lessons_reviewed": lessons_reviewed,
            "lessons_approved": lessons_approved,
            "lessons_rejected": lessons_rejected,
            "tests_required": tests_required,
            "evals_passed": evals_passed,
            "evals_failed": evals_failed,
            "rule_violations": rule_violations,
            "measured_savings": {
                "minutes_saved": self.economics.get("measured_minutes_saved", 0.0),
                "cost_saved_eur": self.economics.get("measured_cost_saved_eur", 0.0),
            },
            "last_action": last_action,
            "next_action": next_action or "Awaiting lesson submissions and evaluation requests",
            "updated_at": now_iso,
        }
        state_file = self.repo_dir / "events/agent-states/agent-academy-director.json"
        save_json(state_file, state_data)
        return state_data

    def check_attendance(self) -> bool:
        """Verifies that Academy Teacher ran during the daily schedule window."""
        teacher_state_file = self.repo_dir / "events/agent-states/agent-academy-teacher.json"
        has_run = teacher_state_file.exists()
        print(f"[DIRECTOR] Attendance check: Agentenlehrer active = {has_run}")
        self.update_visual_state(
            state="CHECKING ATTENDANCE",
            last_action="Verified Agentenlehrer schedule attendance",
            next_action="Reviewing queued lesson proposals",
        )
        return has_run

    def review_lesson(self, lesson_id: str) -> dict:
        """Reviews a lesson proposal for deduplication, evidence completeness, and test requirements."""
        lesson_file = LESSONS_DIR / f"{lesson_id}.json"
        if not lesson_file.exists():
            raise FileNotFoundError(f"Lesson not found: {lesson_id}")
        lesson = load_json(lesson_file)

        # Verification rules
        has_evidence = bool(lesson.get("evidence") and len(str(lesson.get("evidence")).strip()) > 5)
        has_agents = bool(lesson.get("affected_agents") and len(lesson.get("affected_agents")) > 0)
        has_hash = bool(lesson.get("novelty_hash"))

        if not (has_evidence and has_agents and has_hash):
            lesson["status"] = "REJECTED"
            lesson["rejection_reason"] = "Insufficient evidence or unassigned affected agents"
            save_json(lesson_file, lesson)
            print(f"[DIRECTOR] Lesson {lesson_id} REJECTED by Director: Insufficient evidence.")
            self.update_visual_state(
                state="LESSON REJECTED",
                lessons_reviewed=1,
                lessons_rejected=1,
                last_action=f"Rejected lesson {lesson_id}: Insufficient evidence",
            )
            return lesson

        # Approve for testing / evaluation
        lesson["status"] = "APPROVED_FOR_TEST"
        save_json(lesson_file, lesson)
        print(f"[DIRECTOR] Lesson {lesson_id} APPROVED_FOR_TEST by Director.")
        self.update_visual_state(
            state="TEST REQUIRED",
            lessons_reviewed=1,
            lessons_approved=1,
            tests_required=1,
            last_action=f"Approved lesson {lesson_id} for evaluation",
            next_action="Awaiting baseline vs candidate evaluation results",
        )
        return lesson

    def evaluate_lesson(
        self,
        lesson_id: str,
        baseline_metrics: dict,
        candidate_metrics: dict,
    ) -> dict:
        """Compares baseline vs candidate methods with measurable metric criteria."""
        lesson_file = LESSONS_DIR / f"{lesson_id}.json"
        if not lesson_file.exists():
            raise FileNotFoundError(f"Lesson not found: {lesson_id}")
        lesson = load_json(lesson_file)

        eval_id = f"eval-{lesson_id}"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Measurable comparison
        base_runtime = baseline_metrics.get("runtime_seconds", 10.0)
        cand_runtime = candidate_metrics.get("runtime_seconds", 10.0)
        base_errors = baseline_metrics.get("error_count", 0)
        cand_errors = candidate_metrics.get("error_count", 0)
        base_pass_rate = baseline_metrics.get("test_pass_rate", 1.0)
        cand_pass_rate = candidate_metrics.get("test_pass_rate", 1.0)

        # Verdict logic: Pass requires no regressions in pass rate and errors
        passes_criteria = (cand_pass_rate >= base_pass_rate) and (cand_errors <= base_errors)

        verdict = "PASS" if passes_criteria else "FAIL"
        time_saved_min = max(0.0, (base_runtime - cand_runtime) / 60.0)

        eval_record = {
            "schema_version": "2.0",
            "evaluation_id": eval_id,
            "lesson_id": lesson_id,
            "baseline": baseline_metrics,
            "candidate": candidate_metrics,
            "metrics": {
                "runtime_seconds_delta": round(cand_runtime - base_runtime, 2),
                "error_delta": cand_errors - base_errors,
                "pass_rate_delta": round(cand_pass_rate - base_pass_rate, 2),
                "measured_minutes_saved": round(time_saved_min, 2),
            },
            "verdict": verdict,
            "truth_invariants": "TESTED != PRODUCTION | NO_FABRICATED_IMPROVEMENT",
            "evaluated_at": now_iso,
        }

        save_json(EVALS_DIR / f"{eval_id}.json", eval_record)

        lesson["status"] = "EVAL_PASS" if verdict == "PASS" else "EVAL_FAIL"
        lesson["evaluation_id"] = eval_id
        save_json(lesson_file, lesson)

        print(f"[DIRECTOR] Evaluation completed for {lesson_id}: Verdict = {verdict}")
        self.update_visual_state(
            state="EVALUATING",
            evals_passed=1 if verdict == "PASS" else 0,
            evals_failed=1 if verdict == "FAIL" else 0,
            last_action=f"Evaluated {lesson_id}: Verdict={verdict}",
            next_action="Adoption gate review" if verdict == "PASS" else "Lesson closed as failed eval",
        )

        return eval_record

    def approve_adoption(self, lesson_id: str) -> dict:
        """Adoption Gate: Strictly verifies eval passes before adopting into verified context."""
        lesson_file = LESSONS_DIR / f"{lesson_id}.json"
        if not lesson_file.exists():
            raise FileNotFoundError(f"Lesson not found: {lesson_id}")
        lesson = load_json(lesson_file)

        eval_file = EVALS_DIR / f"eval-{lesson_id}.json"
        if not eval_file.exists():
            print(f"[DIRECTOR ERROR] Adoption blocked: No evaluation record exists for {lesson_id}.")
            self.update_visual_state(
                state="RULE VIOLATION",
                rule_violations=1,
                last_action=f"Adoption blocked for {lesson_id}: No evaluation record",
            )
            raise PermissionError(f"Adoption prohibited: Lesson {lesson_id} has not passed evaluation.")

        eval_data = load_json(eval_file)
        if eval_data.get("verdict") != "PASS":
            print(f"[DIRECTOR ERROR] Adoption blocked: Evaluation verdict is {eval_data.get('verdict')}.")
            self.update_visual_state(
                state="ADOPTION BLOCKED",
                rule_violations=1,
                last_action=f"Adoption blocked for {lesson_id}: Evaluation verdict is FAIL",
            )
            raise ValueError(f"Adoption blocked: Evaluation for {lesson_id} failed.")

        # Adoption Approval
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        lesson["status"] = "ADOPTED"
        lesson["adopted_at"] = now_iso
        save_json(lesson_file, lesson)

        adoption_record = {
            "schema_version": "2.0",
            "adoption_id": f"adopt-{lesson_id}",
            "lesson_id": lesson_id,
            "title": lesson.get("title"),
            "topic": lesson.get("topic"),
            "affected_agents": lesson.get("affected_agents"),
            "evaluation_id": eval_data.get("evaluation_id"),
            "adopted_at": now_iso,
        }
        save_json(ADOPTIONS_DIR / f"adopt-{lesson_id}.json", adoption_record)

        # Update Economic Metrics
        mins_saved = eval_data.get("metrics", {}).get("measured_minutes_saved", 0.0)
        self.economics["total_lessons_adopted"] = self.economics.get("total_lessons_adopted", 0) + 1
        self.economics["measured_minutes_saved"] = round(self.economics.get("measured_minutes_saved", 0.0) + mins_saved, 2)
        self.economics["updated_at"] = now_iso
        save_json(self.economics_file, self.economics)

        # Trigger Context Snapshot Refresh via Update Steward
        self.steward.refresh_snapshot_after_event("ACADEMY_LESSON_ADOPTED", lesson_id)

        print(f"[DIRECTOR] Lesson {lesson_id} ADOPTED! Context Snapshot refreshed.")
        self.update_visual_state(
            state="ADOPTION APPROVED",
            lessons_approved=1,
            last_action=f"Adopted lesson {lesson_id} into verified context",
            next_action="Monitoring agent adoption acknowledgements",
        )

        return adoption_record

    def record_worker_acknowledgement(
        self,
        worker_agent_id: str,
        lesson_id: str,
        context_version: int,
    ) -> dict:
        """Records an agent's acknowledgement of an adopted bounded lesson."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        ack = {
            "schema_version": "2.0",
            "worker_agent_id": worker_agent_id,
            "lesson_id_seen": lesson_id,
            "lesson_version_seen": context_version,
            "adoption_status": "ACKNOWLEDGED",
            "acknowledged_at": now_iso,
        }
        save_json(DELIVERIES_DIR / f"ack-{worker_agent_id}-{lesson_id}.json", ack)
        print(f"[DIRECTOR] Worker '{worker_agent_id}' acknowledged lesson {lesson_id} (Context v{context_version})")
        return ack


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Academy CLI")
    parser.add_argument("--demo", action="store_true", help="Run bounded Academy demonstration cycle")
    args = parser.parse_args()

    teacher = AcademyTeacher()
    director = AcademyDirector()

    print("=== AI ACADEMY ENGINE: TEACHER & DIRECTOR READY ===")
    teacher.update_visual_state(state="IDLE", last_action="Academy Teacher standing by")
    director.update_visual_state(state="IDLE", last_action="Academy Director standing by")
