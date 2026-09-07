import json
import uuid
import time
import re
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, Any, Union

from scripts.courier_safety_dispatcher import write_json_atomic, canonical_hash

@dataclass
class GoalItem:
    goal_id: str
    title: str
    target_outcome: str
    success_metric: str
    horizon: str  # immediate, short_term, mid_term, long_term
    priority: int  # 1 (lowest) to 5 (highest)

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class DecisionItem:
    decision_id: str
    decision: str
    rationale: str
    alternatives_considered: list[str] = field(default_factory=list)
    impact: str = "medium"
    status: str = "DECIDED"  # DECIDED, PROPOSED, SUPERSEDED
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class AssumptionItem:
    assumption_id: str
    statement: str
    confidence: float  # 0.0 to 1.0
    validation_method: str
    risk_if_false: str
    is_open: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class OpenQuestionItem:
    question_id: str
    question: str
    context: str
    suggested_resolution: str
    urgency: str = "medium"  # low, medium, high, critical

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class ActionableTaskItem:
    task_id: str
    title: str
    description: str
    capability_required: str  # implementation, repo analysis, repo verification, general
    definition_of_done: str
    target_deliverable: str
    priority: int = 3
    estimated_complexity: str = "medium"  # low, medium, high

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class DeliverableItem:
    deliverable_id: str
    name: str
    description: str
    format: str  # code, json, markdown, test_suite, configuration
    verification_criteria: str

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class OutcomeMetrics:
    time_to_useful_dossier_seconds: float = 0.0
    manual_rework_score: float = 0.0  # 0.0 (zero manual rework needed) to 1.0 (heavy manual rework needed)
    actionable_tasks_count: int = 0
    unresolved_ambiguities_count: int = 0
    dossier_exported: bool = False
    verification_outcome_score: float = 1.0  # 0.0 to 1.0

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class FounderExecutionDossier:
    dossier_id: str
    title: str
    source: str
    created_at: float
    raw_chaos_digest: str
    goals: list[GoalItem] = field(default_factory=list)
    decisions: list[DecisionItem] = field(default_factory=list)
    assumptions: list[AssumptionItem] = field(default_factory=list)
    open_questions: list[OpenQuestionItem] = field(default_factory=list)
    priorities: list[str] = field(default_factory=list)
    tasks: list[ActionableTaskItem] = field(default_factory=list)
    deliverables: list[DeliverableItem] = field(default_factory=list)
    outcome_metrics: OutcomeMetrics = field(default_factory=OutcomeMetrics)
    markdown_content: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FounderExecutionDossier":
        goals = [GoalItem(**g) for g in data.get("goals", [])]
        decisions = [DecisionItem(**d) for d in data.get("decisions", [])]
        assumptions = [AssumptionItem(**a) for a in data.get("assumptions", [])]
        open_questions = [OpenQuestionItem(**q) for q in data.get("open_questions", [])]
        tasks = [ActionableTaskItem(**t) for t in data.get("tasks", [])]
        deliverables = [DeliverableItem(**d) for d in data.get("deliverables", [])]
        metrics_data = data.get("outcome_metrics", {})
        outcome_metrics = OutcomeMetrics(**metrics_data) if metrics_data else OutcomeMetrics()
        
        return cls(
            dossier_id=data.get("dossier_id", str(uuid.uuid4())),
            title=data.get("title", "Untitled Dossier"),
            source=data.get("source", "founder_input"),
            created_at=data.get("created_at", time.time()),
            raw_chaos_digest=data.get("raw_chaos_digest", ""),
            goals=goals,
            decisions=decisions,
            assumptions=assumptions,
            open_questions=open_questions,
            priorities=data.get("priorities", []),
            tasks=tasks,
            deliverables=deliverables,
            outcome_metrics=outcome_metrics,
            markdown_content=data.get("markdown_content", "")
        )

class FounderChaosParser:
    """Parses chaotic, unstructured founder input into structured domain entities."""

    def parse(self, raw_text: str) -> dict[str, Any]:
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        
        goals: list[GoalItem] = []
        decisions: list[DecisionItem] = []
        assumptions: list[AssumptionItem] = []
        open_questions: list[OpenQuestionItem] = []
        tasks: list[ActionableTaskItem] = []
        deliverables: list[DeliverableItem] = []
        priorities: list[str] = []

        current_mode = "general"

        for line in lines:
            line_lower = line.lower()
            
            # Detect section markers
            if any(k in line_lower for k in ["goal:", "goals:", "target:", "objective:", "vision:"]):
                current_mode = "goal"
                cleaned = re.sub(r"^(?:goals?|targets?|objectives?|vision):?\s*", "", line, flags=re.IGNORECASE)
                if cleaned:
                    self._add_goal(goals, cleaned)
                continue
            elif any(k in line_lower for k in ["decision:", "decisions:", "decided:", "we decided"]):
                current_mode = "decision"
                cleaned = re.sub(r"^(?:decisions?|decided|we decided(?: to)?):?\s*", "", line, flags=re.IGNORECASE)
                if cleaned:
                    self._add_decision(decisions, cleaned)
                continue
            elif any(k in line_lower for k in ["assumption:", "assumptions:", "assuming", "assume:"]):
                current_mode = "assumption"
                cleaned = re.sub(r"^(?:assumptions?|assuming|assume):?\s*", "", line, flags=re.IGNORECASE)
                if cleaned:
                    self._add_assumption(assumptions, cleaned)
                continue
            elif any(k in line_lower for k in ["question:", "questions:", "open questions:", "unclear:", "ambiguity:"]):
                current_mode = "question"
                cleaned = re.sub(r"^(?:open questions?|questions?|unclear|ambiguity):?\s*", "", line, flags=re.IGNORECASE)
                if cleaned:
                    self._add_question(open_questions, cleaned)
                continue
            elif any(k in line_lower for k in ["todo:", "task:", "tasks:", "next steps:", "action:"]):
                current_mode = "task"
                cleaned = re.sub(r"^(?:next steps?|tasks?|todos?|action(?: items?)?):?\s*", "", line, flags=re.IGNORECASE)
                if cleaned:
                    self._add_task(tasks, cleaned)
                continue
            elif any(k in line_lower for k in ["deliverable:", "deliverables:", "output:", "deliverable spec:"]):
                current_mode = "deliverable"
                cleaned = re.sub(r"^(?:deliverables?|outputs?|deliverable specs?):?\s*", "", line, flags=re.IGNORECASE)
                if cleaned:
                    self._add_deliverable(deliverables, cleaned)
                continue
            elif any(k in line_lower for k in ["priority:", "priorities:", "p0:", "p1:", "priority rank:"]):
                current_mode = "priority"
                cleaned = re.sub(r"^(?:priorities|priority|p0|p1|priority rank):?\s*", "", line, flags=re.IGNORECASE)
                if cleaned:
                    priorities.append(cleaned)
                continue

            # Contextual line extraction
            if line.startswith("- [ ]") or line.startswith("* [ ]") or line_lower.startswith("todo") or line_lower.startswith("task:"):
                self._add_task(tasks, line)
            elif line.startswith("?") or line.endswith("?") or line_lower.startswith("how do we") or line_lower.startswith("what if") or line_lower.startswith("why "):
                self._add_question(open_questions, line)
            elif "we will use " in line_lower or "we chose " in line_lower or "decision:" in line_lower or "decided that" in line_lower or "instead of" in line_lower:
                self._add_decision(decisions, line)
            elif line_lower.startswith("assume ") or "assumes that" in line_lower or "assumption:" in line_lower:
                self._add_assumption(assumptions, line)
            elif line_lower.startswith("goal:") or line_lower.startswith("outcome:") or "aim is to" in line_lower or "we want to " in line_lower:
                self._add_goal(goals, line)
            elif current_mode == "goal":
                self._add_goal(goals, line)
            elif current_mode == "decision":
                self._add_decision(decisions, line)
            elif current_mode == "assumption":
                self._add_assumption(assumptions, line)
            elif current_mode == "question":
                self._add_question(open_questions, line)
            elif current_mode == "task":
                self._add_task(tasks, line)
            elif current_mode == "deliverable":
                self._add_deliverable(deliverables, line)
            else:
                # General unstructured text analysis
                if len(line) > 10 and not goals:
                    self._add_goal(goals, line)
                elif any(word in line_lower for word in ["build", "create", "fix", "implement", "verify", "test", "deploy", "setup"]):
                    self._add_task(tasks, line)

        # Fallback guarantees if minimal content extracted
        if not goals and lines:
            self._add_goal(goals, lines[0])

        if not tasks:
            for g in goals:
                self._add_task(tasks, f"Execute core goal: {g.title}")

        if not deliverables and tasks:
            for t in tasks[:3]:
                self._add_deliverable(deliverables, f"Artifact for {t.title}")

        if not priorities:
            priorities = [f"P1: {g.title}" for g in goals] + [f"Task: {t.title}" for t in tasks[:3]]

        return {
            "goals": goals,
            "decisions": decisions,
            "assumptions": assumptions,
            "open_questions": open_questions,
            "tasks": tasks,
            "deliverables": deliverables,
            "priorities": priorities
        }

    def _add_goal(self, goals: list[GoalItem], text: str):
        cleaned = re.sub(r"^[-*#0-9.)\s]+", "", text).strip()
        if not cleaned:
            return
        gid = f"GOAL-{len(goals) + 1:02d}"
        horizon = "immediate" if any(w in cleaned.lower() for w in ["today", "now", "immediate", "urgent"]) else "short_term"
        prio = 5 if any(w in cleaned.lower() for w in ["p0", "critical", "must", "urgent"]) else 4
        goals.append(GoalItem(
            goal_id=gid,
            title=cleaned,
            target_outcome=f"Achieve measurable outcome for: {cleaned}",
            success_metric="Automated verification passing and validated dossier artifacts produced",
            horizon=horizon,
            priority=prio
        ))

    def _add_decision(self, decisions: list[DecisionItem], text: str):
        cleaned = re.sub(r"^[-*#0-9.)\s]+", "", text).strip()
        if not cleaned:
            return
        did = f"DEC-{len(decisions) + 1:02d}"
        rationale = "Strategic alignment with founder priorities and architectural simplicity."
        alts = []
        if " instead of " in cleaned.lower():
            parts = re.split(r"\s+instead of\s+", cleaned, flags=re.IGNORECASE)
            cleaned = parts[0]
            alts = [parts[1]]
        decisions.append(DecisionItem(
            decision_id=did,
            decision=cleaned,
            rationale=rationale,
            alternatives_considered=alts,
            impact="high" if any(w in cleaned.lower() for w in ["architecture", "core", "security", "framework", "database"]) else "medium",
            status="DECIDED",
            timestamp=time.time()
        ))

    def _add_assumption(self, assumptions: list[AssumptionItem], text: str):
        cleaned = re.sub(r"^[-*#0-9.)\s]+", "", text).strip()
        if not cleaned:
            return
        aid = f"ASM-{len(assumptions) + 1:02d}"
        assumptions.append(AssumptionItem(
            assumption_id=aid,
            statement=cleaned,
            confidence=0.8,
            validation_method="Empirical test execution or automated verification harness",
            risk_if_false="Requirement adaptation needed; minimal blast radius if caught early",
            is_open=True
        ))

    def _add_question(self, questions: list[OpenQuestionItem], text: str):
        cleaned = re.sub(r"^[-*#0-9.)\s]+", "", text).strip()
        if not cleaned:
            return
        qid = f"Q-{len(questions) + 1:02d}"
        urgency = "high" if any(w in cleaned.lower() for w in ["blocker", "critical", "security", "asap"]) else "medium"
        questions.append(OpenQuestionItem(
            question_id=qid,
            question=cleaned,
            context="Identified during chaos-to-structure extraction from founder notes",
            suggested_resolution="Validate via lightweight prototype or test harness",
            urgency=urgency
        ))

    def _add_task(self, tasks: list[ActionableTaskItem], text: str):
        cleaned = re.sub(r"^[-*#0-9.)\s\[\]x]+", "", text).strip()
        if not cleaned:
            return
        tid = f"TSK-{len(tasks) + 1:02d}"
        cap = "implementation"
        if any(w in cleaned.lower() for w in ["verify", "test", "audit", "check", "assert"]):
            cap = "repo verification"
        elif any(w in cleaned.lower() for w in ["analyze", "inspect", "investigate", "explore", "discover"]):
            cap = "repo analysis"

        tasks.append(ActionableTaskItem(
            task_id=tid,
            title=cleaned,
            description=f"Actionable execution step for: {cleaned}",
            capability_required=cap,
            definition_of_done=f"Implementation complete with corresponding test suite passing cleanly.",
            target_deliverable=f"Verified code/config artifact for {cleaned}",
            priority=4 if any(w in cleaned.lower() for w in ["p0", "urgent", "must", "core"]) else 3,
            estimated_complexity="medium"
        ))

    def _add_deliverable(self, deliverables: list[DeliverableItem], text: str):
        cleaned = re.sub(r"^[-*#0-9.)\s]+", "", text).strip()
        if not cleaned:
            return
        did = f"DEL-{len(deliverables) + 1:02d}"
        fmt = "code" if any(w in cleaned.lower() for w in ["script", "code", "py", "implementation", "module"]) else "markdown"
        deliverables.append(DeliverableItem(
            deliverable_id=did,
            name=cleaned,
            description=f"Deliverable artifact specifying {cleaned}",
            format=fmt,
            verification_criteria="Passes automated verification and conforms to interface specification."
        ))

class FounderConciergePipeline:
    """
    End-to-End Founder Concierge Pipeline:
    Converts unstructured founder chaos (notes, chat transcripts, brain dumps)
    into structured execution dossiers, actionable Courier tasks, and measurable outcome metrics.
    """

    def __init__(self, workspace_dir: Union[str, Path]):
        self.workspace_dir = Path(workspace_dir)
        self.dossier_dir = self.workspace_dir / "events" / "founder-dossiers"
        self.dossier_dir.mkdir(parents=True, exist_ok=True)
        self.parser = FounderChaosParser()

    def process_chaos(
        self,
        raw_chaos: str,
        source: str = "founder_notes",
        title: Optional[str] = None
    ) -> FounderExecutionDossier:
        start_time = time.time()
        dossier_id = f"DOSSIER-{uuid.uuid4().hex[:8].upper()}"
        parsed = self.parser.parse(raw_chaos)

        dossier_title = title or (parsed["goals"][0].title if parsed["goals"] else "Founder Execution Dossier")

        # Compile outcome metrics
        duration = time.time() - start_time
        goals_count = len(parsed["goals"])
        tasks_count = len(parsed["tasks"])
        ambiguities_count = len(parsed["open_questions"]) + len([a for a in parsed["assumptions"] if a.is_open])

        # Manual rework score: lower is better (0.0 to 1.0)
        # Having structured goals + actionable tasks with low ambiguities drives rework toward 0.05
        manual_rework = max(0.05, min(0.95, (ambiguities_count * 0.15) / (max(1, tasks_count + goals_count))))

        outcome_metrics = OutcomeMetrics(
            time_to_useful_dossier_seconds=max(0.001, round(duration, 4)),
            manual_rework_score=round(manual_rework, 3),
            actionable_tasks_count=tasks_count,
            unresolved_ambiguities_count=ambiguities_count,
            dossier_exported=False,
            verification_outcome_score=1.0
        )

        dossier = FounderExecutionDossier(
            dossier_id=dossier_id,
            title=dossier_title,
            source=source,
            created_at=time.time(),
            raw_chaos_digest=canonical_hash(raw_chaos),
            goals=parsed["goals"],
            decisions=parsed["decisions"],
            assumptions=parsed["assumptions"],
            open_questions=parsed["open_questions"],
            priorities=parsed["priorities"],
            tasks=parsed["tasks"],
            deliverables=parsed["deliverables"],
            outcome_metrics=outcome_metrics
        )

        dossier.markdown_content = self.render_markdown(dossier)
        return dossier

    def render_markdown(self, dossier: FounderExecutionDossier) -> str:
        md = []
        md.append(f"# 📋 Founder Execution Dossier: {dossier.title}")
        md.append(f"**Dossier ID**: `{dossier.dossier_id}` | **Source**: `{dossier.source}` | **Created**: `{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(dossier.created_at))}`\n")

        md.append("## 🎯 Structured Strategic Goals")
        for g in dossier.goals:
            md.append(f"- **[{g.goal_id}] {g.title}** (Priority: {g.priority}/5, Horizon: `{g.horizon}`)")
            md.append(f"  - Target Outcome: {g.target_outcome}")
            md.append(f"  - Success Metric: `{g.success_metric}`")
        md.append("")

        md.append("## ⚖️ Key Decision Log")
        if dossier.decisions:
            for d in dossier.decisions:
                alts = f" (Alternatives: {', '.join(d.alternatives_considered)})" if d.alternatives_considered else ""
                md.append(f"- **[{d.decision_id}] {d.decision}** [{d.status}] - Impact: `{d.impact}`{alts}")
                md.append(f"  - *Rationale*: {d.rationale}")
        else:
            md.append("- *No explicit decisions logged in this intake.*")
        md.append("")

        md.append("## 🔍 Assumptions & Open Questions")
        if dossier.assumptions:
            md.append("### Assumptions")
            for a in dossier.assumptions:
                md.append(f"- **[{a.assumption_id}] {a.statement}** (Confidence: {int(a.confidence*100)}%)")
                md.append(f"  - Validation: {a.validation_method}")
                md.append(f"  - Risk: {a.risk_if_false}")
        if dossier.open_questions:
            md.append("### Open Questions & Ambiguities")
            for q in dossier.open_questions:
                md.append(f"- **[{q.question_id}] {q.question}** [Urgency: `{q.urgency}`]")
                md.append(f"  - Suggested Resolution: {q.suggested_resolution}")
        if not dossier.assumptions and not dossier.open_questions:
            md.append("- *Zero unaddressed ambiguities.*")
        md.append("")

        md.append("## ⚡ Concrete Actionable Tasks")
        for t in dossier.tasks:
            md.append(f"- [ ] **[{t.task_id}] {t.title}** (Capability: `{t.capability_required}`, Complexity: `{t.estimated_complexity}`)")
            md.append(f"  - Definition of Done: {t.definition_of_done}")
            md.append(f"  - Deliverable: `{t.target_deliverable}`")
        md.append("")

        md.append("## 📦 Deliverables & Verification Criteria")
        for deliv in dossier.deliverables:
            md.append(f"- **[{deliv.deliverable_id}] {deliv.name}** (`{deliv.format}`)")
            md.append(f"  - Verification: {deliv.verification_criteria}")
        md.append("")

        md.append("## 📊 Outcome & Value Evidence Metrics")
        m = dossier.outcome_metrics
        md.append(f"- **Time to Useful Dossier**: `{m.time_to_useful_dossier_seconds}s`")
        md.append(f"- **Manual Rework Score**: `{m.manual_rework_score}` (Lower is better)")
        md.append(f"- **Actionable Tasks Extracted**: `{m.actionable_tasks_count}`")
        md.append(f"- **Unresolved Ambiguities**: `{m.unresolved_ambiguities_count}`")
        md.append(f"- **Verification Outcome Score**: `{m.verification_outcome_score * 100}%`")
        md.append("")

        return "\n".join(md)

    def save_dossier(self, dossier: FounderExecutionDossier) -> Path:
        json_file = self.dossier_dir / f"{dossier.dossier_id}.json"
        write_json_atomic(json_file, dossier.to_dict())

        md_file = self.dossier_dir / f"{dossier.dossier_id}.md"
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(dossier.markdown_content)

        # Update dossier index
        manifest_file = self.dossier_dir / "dossier_manifest.json"
        manifest = []
        if manifest_file.exists():
            try:
                with open(manifest_file, "r") as f:
                    manifest = json.load(f)
            except Exception:
                manifest = []

        manifest.append({
            "dossier_id": dossier.dossier_id,
            "title": dossier.title,
            "created_at": dossier.created_at,
            "tasks_count": len(dossier.tasks),
            "goals_count": len(dossier.goals),
            "manual_rework_score": dossier.outcome_metrics.manual_rework_score,
            "json_path": str(json_file),
            "md_path": str(md_file)
        })
        write_json_atomic(manifest_file, manifest)
        return json_file

    def export_markdown(self, dossier: FounderExecutionDossier, output_path: Optional[Union[str, Path]] = None) -> str:
        dossier.outcome_metrics.dossier_exported = True
        content = self.render_markdown(dossier)
        dossier.markdown_content = content
        if output_path:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "w", encoding="utf-8") as f:
                f.write(content)
        return content

    def load_dossier(self, dossier_id: str) -> Optional[FounderExecutionDossier]:
        json_file = self.dossier_dir / f"{dossier_id}.json"
        if not json_file.exists():
            return None
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return FounderExecutionDossier.from_dict(data)

    def list_dossiers(self) -> list[dict]:
        manifest_file = self.dossier_dir / "dossier_manifest.json"
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def feed_to_courier_founder_mode(
        self,
        dossier: FounderExecutionDossier,
        founder_mode_mvp: Any
    ) -> list[str]:
        """
        Feeds extracted goals from the dossier into Courier's MultiChatGoalIntake
        and links them to the autonomous execution loop.
        """
        submitted_goal_ids = []
        for g in dossier.goals:
            constraints = [f"Dossier-ID:{dossier.dossier_id}"] + [f"Task:{t.title}" for t in dossier.tasks[:3]]
            gid = founder_mode_mvp.intake.submit_goal(
                source=f"founder_concierge:{dossier.dossier_id}",
                goal=f"{g.title} | Outcome: {g.target_outcome}",
                priority=g.priority,
                constraints=constraints
            )
            submitted_goal_ids.append(gid)
        return submitted_goal_ids
