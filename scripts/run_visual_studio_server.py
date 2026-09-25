#!/usr/bin/env python3
"""Autonomous Chief Operations Cockpit Server for 2026 Courier.

Serves the Studio Web UI and provides real-time state aggregation over the Courier Event Bus:
- /api/state: Aggregates Chief, Antigravity, and Codex visual states, queues, and locks.
- /api/submit-idea: Ingests human ideas/goals and routes them through the Chief Commander.
- /api/human-gate: Persists explicit human approval or rejection events to resume/stop workflows.
- /api/trigger-workflow: Triggers a demonstration multi-round autonomous loop.
"""

from __future__ import annotations

import argparse
import datetime
import http.server
import json
import os
import socketserver
import sys
import threading
import time
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
STUDIO_DIR = COURIER_DIR / "studio"
EVENTS_DIR = COURIER_DIR / "events"

APPROVALS_DIR = EVENTS_DIR / "approvals"
APPROVALS_DIR.mkdir(parents=True, exist_ok=True)

# Add scripts directory to path for imports
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from run_chief_commander import ChiefCommander
    from run_bodyguards import BodyguardPoolManager
    from capability_registry import CapabilityRegistry, SkillRegistry, ConnectorRegistry
    from standing_objectives import StandingObjectivesRegistry
    from resource_intelligence import ResourceIntelligenceManager
    from live_operations_truth_contract import LiveOperationsTruthContract
except ImportError:
    from scripts.run_chief_commander import ChiefCommander
    from scripts.run_bodyguards import BodyguardPoolManager
    from scripts.capability_registry import CapabilityRegistry, SkillRegistry, ConnectorRegistry
    from scripts.standing_objectives import StandingObjectivesRegistry
    from scripts.resource_intelligence import ResourceIntelligenceManager
    from scripts.live_operations_truth_contract import LiveOperationsTruthContract



def load_json_safe(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json_safe(path: Path, data: dict) -> None:
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        print(f"[SERVER] Error saving {path}: {e}")


def _nonempty_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def load_agent_states(states_dir: Path) -> dict[str, dict]:
    """Load machine state without creating an inferred human-gate identity."""
    states: dict[str, dict] = {}
    if not states_dir.exists():
        return states
    for state_file in states_dir.glob("*.json"):
        data = load_json_safe(state_file)
        agent_id = _nonempty_text(data.get("id"))
        if agent_id:
            states[agent_id] = data
    return states


def find_active_human_gate(agents_data: dict[str, dict]) -> dict | None:
    """Return the active gate and only its recorded provenance.

    A legacy gate without workflow/correlation remains visible, but cannot be
    approved or associated with a decision until it has complete provenance.
    """
    for agent_id in sorted(agents_data):
        agent = agents_data[agent_id]
        if agent.get("human_gate") or agent.get("state") in {
            "BLOCKED_HUMAN_GATE", "BLOCKED_POLICY_CONFLICT", "CONFLICT"
        }:
            workflow_id = _nonempty_text(agent.get("workflow"))
            correlation_id = _nonempty_text(agent.get("correlation_id"))
            return {
                "agent_id": agent_id,
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "task_id": _nonempty_text(agent.get("task")),
                "state": _nonempty_text(agent.get("state")) or "UNKNOWN",
                "provenance_complete": bool(workflow_id and correlation_id),
            }
    return None


def resolve_active_gate_decision(gate: dict | None, decisions_dir: Path, approvals_dir: Path) -> dict:
    """Resolve only a decision whose complete provenance matches the gate."""
    result = {
        "status": "NO_DECISION",
        "workflow_id": gate.get("workflow_id") if gate else None,
        "correlation_id": gate.get("correlation_id") if gate else None,
        "source": None,
        "provenance_complete": bool(gate and gate.get("provenance_complete")),
    }
    if not gate or not gate.get("provenance_complete"):
        return result

    candidates: list[tuple[float, str, str]] = []
    for directory, source, field in (
        (decisions_dir, "CHIEF_DECISION", "verdict"),
        (approvals_dir, "HUMAN_APPROVAL", "action"),
    ):
        if not directory.exists():
            continue
        for path in directory.glob("*.json"):
            data = load_json_safe(path)
            if (
                data.get("workflow_id") == gate["workflow_id"]
                and data.get("correlation_id") == gate["correlation_id"]
            ):
                value = _nonempty_text(data.get(field))
                if value:
                    candidates.append((path.stat().st_mtime, source, value))
    if candidates:
        _, source, status = max(candidates, key=lambda item: item[0])
        result.update({"status": status, "source": source})
    return result


class StudioHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STUDIO_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        if self.path == "/api/state":
            self.handle_api_state()
        elif self.path == "/" or self.path == "/index.html":
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/submit-idea":
            self.handle_submit_idea()
        elif self.path == "/api/human-gate":
            self.handle_human_gate()
        elif self.path == "/api/trigger-workflow":
            self.handle_trigger_workflow()
        elif self.path == "/api/trigger-demo":
            self.handle_trigger_demo()
        else:
            self.send_error(404, "Endpoint not found")

    def handle_api_state(self):
        states_dir = EVENTS_DIR / "agent-states"
        agents_data = load_agent_states(states_dir)
        for data in agents_data.values():
            # Ground execution_class strictly in evidence.
            if "execution_class" not in data:
                data["execution_class"] = data.get("result_execution_class", "UNKNOWN")

        dispatch_dir = EVENTS_DIR / "dispatch"
        processed_dir = EVENTS_DIR / "processed"
        decisions_dir = EVENTS_DIR / "chief-decisions"
        locks_dir = EVENTS_DIR / "locks"
        approvals_dir = EVENTS_DIR / "approvals"
        runtime_alerts_dir = EVENTS_DIR / "runtime-alerts"

        counts = {
            "dispatch": len(list(dispatch_dir.glob("*.json"))) if dispatch_dir.exists() else 0,
            "processed": len(list(processed_dir.glob("*.json"))) if processed_dir.exists() else 0,
            "decisions": len(list(decisions_dir.glob("*.json"))) if decisions_dir.exists() else 0,
            "approvals": len(list(approvals_dir.glob("*.json"))) if approvals_dir.exists() else 0,
            "runtime_alerts": len(list(runtime_alerts_dir.glob("*.json"))) if runtime_alerts_dir.exists() else 0,
        }

        active_locks = list(locks_dir.glob("*.lock")) if locks_dir.exists() else []
        is_locked = len(active_locks) > 0
        active_lock_name = active_locks[0].stem if is_locked else None

        # Derive Last Decision Truth
        last_decision = "NO_DECISION"
        if decisions_dir.exists():
            dec_files = sorted(decisions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if dec_files:
                last_dec_data = load_json_safe(dec_files[0])
                last_decision = last_dec_data.get("verdict", "NO_DECISION")

        # Derive Correlation ID Truth (No Synthetic Random Generation, No Workflow Name Derivations)
        derived_correlation_id = "UNKNOWN"
        if is_locked and active_lock_name:
            lock_data = load_json_safe(active_locks[0])
            derived_correlation_id = lock_data.get("correlation_id", "UNKNOWN")
        else:
            recent_files = []
            if dispatch_dir.exists():
                recent_files.extend(dispatch_dir.glob("*.json"))
            if processed_dir.exists():
                recent_files.extend(processed_dir.glob("*.json"))
            if recent_files:
                sorted_events = sorted(recent_files, key=lambda p: p.stat().st_mtime, reverse=True)
                latest_evt = load_json_safe(sorted_events[0])
                derived_correlation_id = latest_evt.get("correlation_id", "UNKNOWN")

        # A gate is active based on machine state.  Its decision may only be
        # attached when both workflow_id and correlation_id match exactly.
        active_human_gate = find_active_human_gate(agents_data)
        human_gate_active = active_human_gate is not None
        gate_decision = resolve_active_gate_decision(
            active_human_gate, decisions_dir, approvals_dir
        )

        latest_runtime_alert = None
        if runtime_alerts_dir.exists():
            alert_files = sorted(runtime_alerts_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if alert_files:
                latest_runtime_alert = load_json_safe(alert_files[0]) or None

        treasury = {
            "eur": None,
            "usd": None,
            "last_verified_at": None,
            "goal_current_usd": 8,
            "goal_target_usd": 1_000_000_000,
            "goal_status": "ASPIRATIONAL_MANUAL_NOT_VERIFIED",
        }

        # Read latest context snapshot
        snapshot_file = EVENTS_DIR / "context-snapshots/snapshot-current.json"
        snapshot_data = load_json_safe(snapshot_file) if snapshot_file.exists() else None

        # Read academy structured evidence
        academy_dir = EVENTS_DIR / "academy"
        academy_data = None
        if academy_dir.exists():
            config_data = load_json_safe(academy_dir / "config.json")
            econ_data = load_json_safe(academy_dir / "economics.json")

            # Collect latest lessons (bounded to latest 15)
            lessons_dir = academy_dir / "lessons"
            recent_lessons = []
            opportunity_candidates = []
            if lessons_dir.exists():
                lfiles = sorted(lessons_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                for lf in lfiles[:15]:
                    ld = load_json_safe(lf)
                    if ld and "lesson_id" in ld:
                        summary_entry = {
                            "lesson_id": ld.get("lesson_id"),
                            "title": ld.get("title"),
                            "topic": ld.get("topic"),
                            "status": ld.get("status", "DISCOVERED"),
                            "lesson_type": ld.get("lesson_type"),
                            "risk": ld.get("risk", "LOW"),
                            "affected_agents": ld.get("affected_agents", []),
                            "expected_benefit": ld.get("expected_benefit"),
                            "discovered_at": ld.get("discovered_at"),
                            "novelty_hash": ld.get("novelty_hash", "")[:12],
                        }
                        recent_lessons.append(summary_entry)
                        if ld.get("lesson_type") == "OPPORTUNITY_CANDIDATE":
                            opportunity_candidates.append({
                                "lesson_id": ld.get("lesson_id"),
                                "title": ld.get("title"),
                                "status": ld.get("status", "DISCOVERED"),
                                "idea_sync_id": ld.get("idea_sync_id"),
                                "evidence": ld.get("evidence"),
                                "revenue_evidence": "NOT_VERIFIED",
                            })

            # Collect latest evaluations (bounded to 10)
            evals_dir = academy_dir / "evaluations"
            recent_evals = []
            if evals_dir.exists():
                efiles = sorted(evals_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                for ef in efiles[:10]:
                    ed = load_json_safe(ef)
                    if ed and "evaluation_id" in ed:
                        recent_evals.append({
                            "evaluation_id": ed.get("evaluation_id"),
                            "lesson_id": ed.get("lesson_id"),
                            "verdict": ed.get("verdict", "UNKNOWN"),
                            "metrics": ed.get("metrics", {}),
                            "evaluated_at": ed.get("evaluated_at"),
                        })

            academy_data = {
                "config": config_data,
                "economics": econ_data,
                "lessons": recent_lessons,
                "opportunities": opportunity_candidates,
                "evaluations": recent_evals,
            }

        # Read SNITCH state and recent incidents
        snitch_file = states_dir / "agent-snitch.json"
        snitch_data = load_json_safe(snitch_file) if snitch_file.exists() else None

        incidents_data = []
        if runtime_alerts_dir.exists():
            alert_files = sorted(runtime_alerts_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            for af in alert_files[:10]:
                ad = load_json_safe(af)
                if ad and "message_id" in ad:
                    incidents_data.append({
                        "message_id": ad.get("message_id"),
                        "incident_id": ad.get("incident_id"),
                        "classification": ad.get("classification"),
                        "severity": ad.get("severity", "MEDIUM"),
                        "status": ad.get("status", "OPEN"),
                        "task_id": ad.get("task_id"),
                        "workflow_id": ad.get("workflow_id"),
                        "correlation_id": ad.get("correlation_id"),
                        "reason": ad.get("reason"),
                        "created_at": ad.get("created_at"),
                    })

        # Read 8 Bodyguards reserve states
        try:
            bodyguards_data = BodyguardPoolManager(COURIER_DIR).get_all_bodyguards()
        except Exception:
            bodyguards_data = []

        # Read Transport State
        transport_dir = EVENTS_DIR / "transport"
        transport_data = None
        if transport_dir.exists():
            reg_file = transport_dir / "registry.json"
            reg_data = load_json_safe(reg_file) if reg_file.exists() else {}
            trans_log = transport_dir / "transitions.jsonl"
            latest_transition = None
            if trans_log.exists():
                try:
                    lines = trans_log.read_text(encoding="utf-8").strip().splitlines()
                    if lines:
                        latest_transition = json.loads(lines[-1])
                except Exception:
                    pass
            transport_data = {
                "incoming_count": len(list((transport_dir / "incoming").glob("*.json"))) if (transport_dir / "incoming").exists() else 0,
                "processed_count": len(list((transport_dir / "processed").glob("*.json"))) if (transport_dir / "processed").exists() else 0,
                "rejected_count": len(list((transport_dir / "rejected").glob("*.json"))) if (transport_dir / "rejected").exists() else 0,
                "ack_count": len(list((transport_dir / "acknowledgements").glob("*.json"))) if (transport_dir / "acknowledgements").exists() else 0,
                "registry": reg_data,
                "latest_transition": latest_transition,
            }

        # Read Review Budget & Ledger State
        reviews_dir = EVENTS_DIR / "reviews"
        review_budget_data = None
        if reviews_dir.exists():
            rev_ledger_file = reviews_dir / "ledger.json"
            rev_data = load_json_safe(rev_ledger_file) if rev_ledger_file.exists() else {}
            today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
            review_budget_data = {
                "total_reviews": rev_data.get("stats", {}).get("total_reviews", 0),
                "total_reused": rev_data.get("stats", {}).get("total_reused", 0),
                "daily_routine_batches_today": rev_data.get("daily_batches", {}).get(today_str, 0),
                "max_routine_batches_per_day": 1,
                "policy": load_json_safe(EVENTS_DIR / "policies" / "review_policy.json") or {},
            }

        # Read Capability, Skill & Connector Registries
        try:
            capabilities_data = CapabilityRegistry(COURIER_DIR).export_summary()
            skills_data = [s.to_dict() for s in SkillRegistry(COURIER_DIR).list_active_skills()]
            connectors_data = ConnectorRegistry(COURIER_DIR).export_summary()
        except Exception:
            capabilities_data = {}
            skills_data = []
            connectors_data = {}

        # Read active handoffs if any
        handoffs_dir = EVENTS_DIR / "handoffs"
        active_handoffs = []
        if handoffs_dir.exists():
            for hf in sorted(handoffs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
                hd = load_json_safe(hf)
                if hd and "handoff_id" in hd:
                    active_handoffs.append(hd)

        # Read Chief Presence
        presence_file = EVENTS_DIR / "chief_presence.json"
        chief_presence_data = load_json_safe(presence_file) or {"presence": "AWAKE"}

        # Read Standing Objectives
        try:
            standing_objectives_data = StandingObjectivesRegistry(COURIER_DIR).export_summary()
        except Exception:
            standing_objectives_data = {}

        # Resource capacity is local telemetry only; absent observations remain UNKNOWN.
        try:
            resource_intelligence_data = ResourceIntelligenceManager(COURIER_DIR).summary()
        except Exception:
            resource_intelligence_data = {"canonical_term": "MODEL_RESOURCE_CAPACITY", "status": "UNKNOWN"}

        # Read Morning Report
        morning_report_file = EVENTS_DIR / "morning-reports/latest_morning_report.json"
        latest_morning_report_data = load_json_safe(morning_report_file)

        # Read Heartbeat Telemetry
        heartbeat_file = EVENTS_DIR / "heartbeat.json"
        heartbeat_data = load_json_safe(heartbeat_file) or {}

        # Read Opportunity Queue Telemetry
        queue_dir = EVENTS_DIR / "opportunity-queue"
        queue_summary = {"READY": 0, "RUNNING": 0, "BLOCKED": 0, "WAITING_FOR_HUMAN": 0, "COMPLETED": 0, "TOTAL": 0}
        if queue_dir.exists():
            for qf in queue_dir.glob("*.json"):
                qd = load_json_safe(qf)
                if qd and "status" in qd:
                    st = qd["status"]
                    queue_summary["TOTAL"] += 1
                    if st in queue_summary:
                        queue_summary[st] += 1
        # Read Autonomy Runtime & 188G Endurance Telemetry (Strict Read-Only)
        autonomy_dir = EVENTS_DIR / "autonomy-runtime"
        autonomy_runtime_data = {
            "status": "IDLE_EXPECTED",
            "session_id": "NONE",
            "current_goal": "Awaiting directive",
            "current_action": "IDLE_EXPECTED",
            "human_gates": [],
            "money_gates": [],
            "jobs_dispatched": [],
            "jobs_completed": [],
            "last_active_at": None,
        }
        endurance_188g_data = {
            "is_running": False,
            "status": "NO_ACTIVE_SESSION",
            "session_id": "NONE",
            "elapsed_seconds": 0.0,
            "remaining_seconds": 0.0,
            "duration_target_hours": 8.0,
            "model_calls_during_idle": 0,
            "autonomous_spend_eur": 0.0,
            "completed_jobs": [],
        }

        if autonomy_dir.exists():
            curr_sess_file = autonomy_dir / "current_session.json"
            if curr_sess_file.exists():
                cs = load_json_safe(curr_sess_file)
                autonomy_runtime_data["status"] = cs.get("status", "IDLE_EXPECTED")
                autonomy_runtime_data["session_id"] = cs.get("session_id", "NONE")
                autonomy_runtime_data["current_goal"] = cs.get("goal", "Awaiting directive")
                autonomy_runtime_data["current_action"] = cs.get("current_action", cs.get("status", "IDLE_EXPECTED"))
                autonomy_runtime_data["human_gates"] = cs.get("human_gates_encountered", [])
                autonomy_runtime_data["money_gates"] = cs.get("money_gates_encountered", [])
                autonomy_runtime_data["jobs_dispatched"] = cs.get("jobs_dispatched", [])
                autonomy_runtime_data["jobs_completed"] = cs.get("jobs_completed", [])
                autonomy_runtime_data["last_active_at"] = cs.get("last_active_at")

            hb_file = autonomy_dir / "heartbeat.json"
            pid_file = autonomy_dir / "supervisor.pid"
            if hb_file.exists():
                hb = load_json_safe(hb_file)
                endurance_188g_data["status"] = hb.get("status", "IDLE_EXPECTED")
                endurance_188g_data["session_id"] = hb.get("session_id", "NONE")
                endurance_188g_data["elapsed_seconds"] = hb.get("elapsed_seconds", 0.0)
                endurance_188g_data["remaining_seconds"] = hb.get("remaining_seconds", 0.0)
                endurance_188g_data["duration_target_hours"] = hb.get("duration_target_hours", 8.0)
                endurance_188g_data["model_calls_during_idle"] = hb.get("model_calls_during_idle", 0)
                endurance_188g_data["autonomous_spend_eur"] = hb.get("autonomous_spend_eur", 0.0)
                endurance_188g_data["completed_jobs"] = autonomy_runtime_data["jobs_completed"]
                endurance_188g_data["is_running"] = pid_file.exists()

        # Read Snitch Anomaly Ledger
        anomalies_dir = EVENTS_DIR / "anomalies"
        anomaly_ledger_data = {"ledger": {}, "quarantined_branches": [], "quarantined_scopes": []}
        if anomalies_dir.exists():
            anom_file = anomalies_dir / "anomaly_ledger.json"
            if anom_file.exists():
                anom_map = load_json_safe(anom_file)
                anomaly_ledger_data["ledger"] = anom_map
                for fp, entry in anom_map.items():
                    if entry.get("severity") == "CRITICAL" and not entry.get("resolved", False):
                        b = entry.get("affected_branch")
                        s = entry.get("affected_scope")
                        if b and b not in anomaly_ledger_data["quarantined_branches"]:
                            anomaly_ledger_data["quarantined_branches"].append(b)
                        if s and s not in anomaly_ledger_data["quarantined_scopes"]:
                            anomaly_ledger_data["quarantined_scopes"].append(s)

        # Read Live Operations Truth Contract (Mission PRODUCT-1C / PRODUCT-2)
        try:
            truth_contract_data = LiveOperationsTruthContract(COURIER_DIR).snapshot()
        except Exception:
            truth_contract_data = {
                "contract_version": "PRODUCT_1C_V1",
                "current_goal": "NOT_AVAILABLE",
                "organization_status": "IDLE",
                "tasks": [],
                "active_task": None,
                "active_agent": None,
                "active_provider": None,
                "anomalies": [],
                "endurance_188g": {"status": "NOT_AVAILABLE", "endurance_proven": "PENDING"},
                "model_calls": 0,
            }

        # Build Real Task Board items
        task_board_items = []
        if queue_dir.exists():
            for qf in sorted(queue_dir.glob("*.json")):
                qd = load_json_safe(qf)
                if qd and "opportunity_id" in qd:
                    oid = qd.get("opportunity_id")
                    task_board_items.append({
                        "task_id": oid,
                        "title": qd.get("description", qd.get("problem_or_goal", oid)),
                        "owner_agent": qd.get("target_agent", "UNKNOWN"),
                        "provider": "GOOGLE_PRO" if qd.get("target_agent") == "antigravity" else ("CODEX" if qd.get("target_agent") == "codex" else "LOCAL_DETERMINISTIC"),
                        "status": qd.get("status", "BACKLOG"),
                        "priority": qd.get("priority", 5),
                        "risk": qd.get("risk", "LOW"),
                        "cost_class": qd.get("cost_class", "FREE_LOCAL"),
                    })

        # Deduplicate and merge with truth contract tasks
        for tc_task in truth_contract_data.get("tasks", []):
            tid = tc_task.get("task_id")
            existing = next((t for t in task_board_items if t["task_id"] == tid), None)
            if existing:
                existing["status"] = tc_task.get("status", existing["status"])
                if tc_task.get("owner_agent"):
                    existing["owner_agent"] = tc_task.get("owner_agent")
                if tc_task.get("provider"):
                    existing["provider"] = tc_task.get("provider")
                existing["last_meaningful_event"] = tc_task.get("last_meaningful_event")
            else:
                task_board_items.append({
                    "task_id": tid,
                    "title": tc_task.get("title", tid),
                    "owner_agent": tc_task.get("owner_agent", "UNKNOWN"),
                    "provider": tc_task.get("provider", "LOCAL_DETERMINISTIC"),
                    "status": tc_task.get("status", "UNKNOWN"),
                    "last_meaningful_event": tc_task.get("last_meaningful_event"),
                })

        # Collect recent meaningful events for the Result Feed
        recent_events = []
        if autonomy_dir.exists():
            event_ledger_file = autonomy_dir / "event_ledger.json"
            if event_ledger_file.exists():
                el = load_json_safe(event_ledger_file)
                for ev in el.get("events", [])[-20:]:
                    recent_events.append({
                        "event_id": ev.get("event_id"),
                        "event_type": ev.get("event_type"),
                        "task_id": ev.get("task_id"),
                        "source_worker": ev.get("source_worker"),
                        "outcome": ev.get("payload", {}).get("outcome") if isinstance(ev.get("payload"), dict) else "UNKNOWN",
                        "ingested_at": ev.get("ingested_at"),
                    })

        # Build Productivity Timeline (meaningful lifecycle events only)
        timeline_events = []
        for ev in recent_events:
            ev_type = ev.get("event_type", "EVENT")
            outcome = ev.get("outcome", "OK")
            tid = ev.get("task_id", "")
            worker = ev.get("source_worker", "")

            label = "WORK_EVENT"
            if ev_type == "RESULT" and outcome == "SUCCESS":
                label = "TASK_COMPLETED"
            elif ev_type == "RESULT" and outcome == "FAIL":
                label = "TASK_FAILED"
            elif ev_type == "HUMAN_GATE":
                label = "HUMAN_GATE"
            elif ev_type == "MONEY_GATE":
                label = "MONEY_GATE"
            elif ev_type == "DISPATCH":
                label = "TASK_ASSIGNED"
            elif ev_type == "START":
                label = "JOB_STARTED"
            elif ev_type == "ANOMALY":
                label = "ANOMALY"

            timeline_events.append({
                "timestamp": ev.get("ingested_at") or datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "event_type": label,
                "task_id": tid,
                "actor": worker or "SYSTEM",
                "details": f"{label} for {tid} (Outcome: {outcome})",
                "status": outcome,
            })

        if not timeline_events:
            timeline_events.append({
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "event_type": "SAFE IDLE",
                "task_id": "NONE",
                "actor": "ORGANIZATION",
                "details": "Organization operating safely in IDLE_EXPECTED state",
                "status": "HEALTHY",
            })

        session_view = {
            "status": autonomy_runtime_data.get("status", "IDLE_EXPECTED"),
            "session_id": autonomy_runtime_data.get("session_id", "NONE"),
            "started_at": autonomy_runtime_data.get("last_active_at") or datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "current_goal": autonomy_runtime_data.get("current_goal", "Autonomous Standby"),
            "current_phase": "EXECUTION" if autonomy_runtime_data.get("status") == "RUNNING" else ("GATE_PAUSE" if "GATE" in str(autonomy_runtime_data.get("status", "")) else "SAFE_IDLE"),
            "current_task": autonomy_runtime_data.get("current_action", "Safe Standby"),
            "next_action": "Wait for evidence unlock or backlog opportunity",
            "active_workers": [t.get("owner_agent") for t in task_board_items if t.get("status") == "ACTIVE"] or [],
            "completed_tasks_count": len(autonomy_runtime_data.get("jobs_completed", [])),
            "waiting_tasks_count": sum(1 for t in task_board_items if t.get("status") in ("WAITING", "BACKLOG", "READY")),
            "failed_tasks_count": sum(1 for t in task_board_items if t.get("status") in ("FAILED", "BLOCKED")),
            "human_gates_count": len(autonomy_runtime_data.get("human_gates", [])),
            "money_gates_count": len(autonomy_runtime_data.get("money_gates", [])),
            "anomalies_count": len(anomaly_ledger_data.get("quarantined_branches", [])),
            "last_useful_result": autonomy_runtime_data["jobs_completed"][-1] if autonomy_runtime_data.get("jobs_completed") else "None",
            "recovery_status": "HEALTHY" if not anomaly_ledger_data.get("quarantined_branches") else "BRANCH_QUARANTINED",
        }

        # Read Real Snitch Observer Telemetry
        snitch_readiness = None
        snitch_worker_observations = []
        try:
            from snitch_observer import SnitchObserver
        except ImportError:
            try:
                from scripts.snitch_observer import SnitchObserver
            except ImportError:
                SnitchObserver = None

        if SnitchObserver:
            try:
                observer = SnitchObserver(repo_dir=COURIER_DIR)
                snitch_readiness = observer.compute_operational_readiness(oracle_test_command=None).to_dict()
                snitch_worker_observations = [w.to_dict() for w in observer.inspect_workspace()]
            except Exception as e:
                snitch_readiness = {"readiness": "UNKNOWN", "safe_for_unattended_operation": False, "reasons": [str(e)]}

        # Check Heavy Scope Lock
        is_heavy_locked = bool(list(locks_dir.glob("scope_HEAVY*.json")))

        # Ingest/Ensure Execution Workers (GOOGLE, CODEX, CLI1, CLI2)
        execution_workers_def = {
            "worker-google": {
                "id": "worker-google",
                "name": "GOOGLE",
                "role": "Google Pro / Primary Builder",
                "provider": "GOOGLE_PRO",
                "state": "PROGRESSING" if any(t.get("provider") == "GOOGLE_PRO" and t.get("status") in ("ACTIVE", "RUNNING") for t in task_board_items) else "SAFE_IDLE",
                "task": next((t.get("title") for t in task_board_items if t.get("provider") == "GOOGLE_PRO" and t.get("status") in ("ACTIVE", "RUNNING")), "Standby"),
                "heavy_job": is_heavy_locked,
                "execution_class": "REAL_ANTIGRAVITY",
            },
            "worker-codex": {
                "id": "worker-codex",
                "name": "CODEX",
                "role": "Codex QA Specialist",
                "provider": "CODEX",
                "state": "PROGRESSING" if any(t.get("provider") == "CODEX" and t.get("status") in ("ACTIVE", "RUNNING") for t in task_board_items) else "SAFE_IDLE",
                "task": next((t.get("title") for t in task_board_items if t.get("provider") == "CODEX" and t.get("status") in ("ACTIVE", "RUNNING")), "Standby"),
                "heavy_job": False,
                "execution_class": "REAL_CODEX_CLI",
            },
            "worker-cli1": {
                "id": "worker-cli1",
                "name": "CLI 1",
                "role": "Primary Terminal Operator",
                "provider": "LOCAL_CLI_1",
                "state": "SAFE_IDLE",
                "task": "Standby (Awaiting Directive)",
                "heavy_job": False,
                "execution_class": "DETERMINISTIC_ANTIGRAVITY",
            },
            "worker-cli2": {
                "id": "worker-cli2",
                "name": "CLI 2",
                "role": "Beata Account Operator",
                "provider": "LOCAL_CLI_2",
                "state": "SAFE_IDLE",
                "task": "Standby (Profile Isolated)",
                "heavy_job": False,
                "execution_class": "DETERMINISTIC_ANTIGRAVITY",
            },
        }

        for wid, wdef in execution_workers_def.items():
            if wid not in agents_data:
                agents_data[wid] = wdef

        response_data = {
            "schema_version": "2.0",
            "server_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "agents": agents_data,
            "snitch_observer": snitch_readiness,
            "snitch_workers": snitch_worker_observations,
            "autonomy_runtime": autonomy_runtime_data,
            "endurance_188g": endurance_188g_data,
            "anomalies": anomaly_ledger_data,
            "truth_contract": truth_contract_data,
            "task_board": task_board_items,
            "result_feed": recent_events,
            "session_view": session_view,
            "productivity_timeline": timeline_events,
            "counts": counts,
            "context_snapshot": snapshot_data,
            "academy": academy_data,
            "snitch": snitch_data,
            "bodyguards": bodyguards_data,
            "incidents": incidents_data,
            "runtime_alert": latest_runtime_alert,
            "treasury": treasury,
            "transport": transport_data,
            "review_budget": review_budget_data,
            "capabilities": capabilities_data,
            "skills": skills_data,
            "connectors": connectors_data,
            "handoffs": active_handoffs,
            "chief_presence": chief_presence_data,
            "standing_objectives": standing_objectives_data,
            "resource_intelligence": resource_intelligence_data,
            "morning_report": latest_morning_report_data,
            "heartbeat": heartbeat_data,
            "opportunity_queue": queue_summary,
            "bus": {
                "is_locked": is_locked,
                "active_lock": active_lock_name,
                "last_decision": last_decision,
                "active_workflow": active_lock_name or "IDLE_MONITORING",
                "correlation_id": derived_correlation_id,
                "human_gate": human_gate_active,
                "active_human_gate": active_human_gate,
                "gate_decision": gate_decision,
                "context_version": snapshot_data.get("context_version") if snapshot_data else 0,
                "snapshot_hash": snapshot_data.get("snapshot_hash") if snapshot_data else "NONE",
            }
        }


        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode("utf-8"))

    def handle_submit_idea(self):
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len).decode("utf-8")
        try:
            req_data = json.loads(post_body)
            idea = req_data.get("idea", "").strip()
            idea_type = req_data.get("type", "IDEA")

            if not idea:
                self.send_error(400, "Empty idea provided")
                return

            def run_async_chief():
                chief = ChiefCommander(repo_dir=COURIER_DIR)
                chief.execute_human_idea(idea, idea_type)

            threading.Thread(target=run_async_chief, daemon=True).start()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "INGESTED",
                "message": f"Human {idea_type} received by Chief Commander and workflow dispatched.",
                "idea": idea,
            }).encode("utf-8"))

        except Exception as exc:
            self.send_error(500, f"Failed to ingest idea: {exc}")

    def handle_human_gate(self):
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len).decode("utf-8")
        try:
            req_data = json.loads(post_body)
            action = req_data.get("action", "").upper()  # "APPROVE" or "REJECT"
            workflow_id = _nonempty_text(req_data.get("workflow_id"))
            correlation_id = _nonempty_text(req_data.get("correlation_id"))
            reason = req_data.get("reason", "Operator decision from Visual Studio Cockpit")

            if action not in ["APPROVE", "REJECT"]:
                self.send_error(400, "Invalid action. Must be APPROVE or REJECT.")
                return

            active_gate = find_active_human_gate(
                load_agent_states(EVENTS_DIR / "agent-states")
            )
            if not active_gate or not active_gate.get("provenance_complete"):
                self.send_error(409, "Human gate has no verified workflow/correlation provenance.")
                return
            if (
                workflow_id != active_gate["workflow_id"]
                or correlation_id != active_gate["correlation_id"]
            ):
                self.send_error(409, "Human gate provenance mismatch.")
                return

            approval_id = f"appr-{uuid.uuid4().hex[:8]}"
            approval_record = {
                "schema_version": "2.0",
                "approval_id": approval_id,
                "action": action,
                "decision": action,
                "workflow_id": workflow_id,
                "task_id": active_gate.get("task_id"),
                "correlation_id": correlation_id,
                "operator": "HUMAN_OPERATOR",
                "reason": reason,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }

            approval_file = APPROVALS_DIR / f"{approval_id}.json"
            save_json_safe(approval_file, approval_record)
            print(f"\n[SERVER] Human Gate Event Persisted: {action} for {workflow_id} ({approval_id})")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "PERSISTED",
                "approval_id": approval_id,
                "action": action,
                "workflow_id": workflow_id,
            }).encode("utf-8"))

        except Exception as exc:
            self.send_error(500, f"Failed to persist human gate action: {exc}")

    def handle_trigger_workflow(self):
        def run_async():
            chief = ChiefCommander(repo_dir=COURIER_DIR)
            chief.execute_human_idea("Demo-Lauf: Optimiere Video-Pipeline und prüfe Channel-Konfigurationen", "GOAL")

        threading.Thread(target=run_async, daemon=True).start()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "TRIGGERED", "message": "Demo workflow started in background"}).encode("utf-8"))

    def handle_trigger_demo(self):
        def run_async_demo():
            from run_demo_workflow import DemoOrchestrator
            orchestrator = DemoOrchestrator(repo_dir=COURIER_DIR)
            orchestrator.reset_demo_environment()
            orchestrator.run_live_demo()

        threading.Thread(target=run_async_demo, daemon=True).start()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "TRIGGERED", "message": "Deterministic live demo workflow started in background"}).encode("utf-8"))


def run_server(port: int = 8088):
    server_address = ("", port)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(server_address, StudioHTTPRequestHandler) as httpd:
        print(f"=== AUTONOMOUS CHIEF OPERATIONS COCKPIT RUNNING ===")
        print(f"Serving at: http://localhost:{port}")
        print(f"Studio Root: {STUDIO_DIR}")
        print(f"Courier Bus: {EVENTS_DIR}")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down Operations Studio server.")


def main():
    parser = argparse.ArgumentParser(description="Run Autonomous Chief Operations Cockpit Server")
    parser.add_argument("--port", type=int, default=8088, help="Port to serve UI (default: 8088)")
    args = parser.parse_args()
    run_server(args.port)


if __name__ == "__main__":
    main()
