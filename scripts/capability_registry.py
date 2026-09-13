#!/usr/bin/env python3
"""Autonomous Agent Capability, Skill, Handoff & Safety Layer (Mission 113).

Provides durable, non-secret capability profiles, action safety classification,
reusable skill registry, controlled routine proposals, agent-to-agent handoffs,
minimal context delta transfer, connector metadata, and resumable human gates.
"""

from __future__ import annotations

import datetime
import enum
import hashlib
import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
EVENTS_DIR = COURIER_DIR / "events"
CONFIG_DIR = COURIER_DIR / "config"
PROCESSED_DIR = EVENTS_DIR / "processed"


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(temp_path, path)


# ============================================================================
# 1. ACTION SAFETY CLASSES & POLICY
# ============================================================================

class ActionSafetyClass(str, enum.Enum):
    READ = "READ"
    WRITE = "WRITE"
    PUBLISH = "PUBLISH"
    DELETE = "DELETE"
    PAYMENT = "PAYMENT"
    IDENTITY = "IDENTITY"
    AUTH = "AUTH"


class SafetyPolicyEvaluator:
    """Evaluates requested operations against action safety classes and fails closed."""

    @staticmethod
    def evaluate_action_safety(
        capability_name: str,
        action_type: str | ActionSafetyClass,
        context: dict | None = None
    ) -> tuple[bool, str, str | None]:
        """Evaluates whether an action is permitted, blocked, or requires a Human Gate.

        Returns:
            tuple of (is_allowed, reason, required_human_gate)
        """
        try:
            safety_class = ActionSafetyClass(action_type)
        except ValueError:
            return False, f"Unknown action safety class '{action_type}' (fail-closed)", "UNKNOWN_ACTION_GATE"

        if safety_class == ActionSafetyClass.DELETE:
            return False, "DELETE actions are DENIED BY DEFAULT across all agents", None

        if safety_class == ActionSafetyClass.PUBLISH:
            return False, f"PUBLISH action for capability '{capability_name}' requires human approval", "PUBLICATION_GATE"

        if safety_class == ActionSafetyClass.PAYMENT:
            return False, f"PAYMENT action for capability '{capability_name}' requires human approval", "PAYMENT_GATE"

        if safety_class == ActionSafetyClass.IDENTITY:
            return False, f"IDENTITY modification for capability '{capability_name}' requires human approval", "IDENTITY_GATE"

        if safety_class == ActionSafetyClass.AUTH:
            return False, f"AUTH / Login / OAuth / 2FA for capability '{capability_name}' requires human approval", "AUTH_GATE"

        if safety_class == ActionSafetyClass.WRITE:
            # Policy controlled write
            if context and context.get("write_policy") == "DENY":
                return False, f"WRITE action denied by local context policy for '{capability_name}'", None
            return True, f"WRITE action allowed under policy control for '{capability_name}'", None

        if safety_class == ActionSafetyClass.READ:
            return True, f"READ action allowed for capability '{capability_name}'", None

        return False, f"Unhandled action class '{safety_class}' (fail-closed)", "SAFETY_GATE"


# ============================================================================
# 2. CAPABILITY REGISTRY
# ============================================================================

class CapabilityState(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    PAUSED = "PAUSED"


@dataclass
class Capability:
    name: str
    state: CapabilityState
    evidence: str
    safety_class: ActionSafetyClass
    last_verified: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class CapabilityRegistry:
    """Canonical deterministic registry of agent capabilities."""

    DEFAULT_CAPABILITIES: dict[str, Capability] = {
        "LOCAL_FILES_READ": Capability("LOCAL_FILES_READ", CapabilityState.AVAILABLE, "Local repository filesystem read access verified", ActionSafetyClass.READ),
        "LOCAL_FILES_WRITE": Capability("LOCAL_FILES_WRITE", CapabilityState.AVAILABLE, "Local repository filesystem write access verified", ActionSafetyClass.WRITE),
        "GIT_READ": Capability("GIT_READ", CapabilityState.AVAILABLE, "Local git status/log inspection verified", ActionSafetyClass.READ),
        "GIT_WRITE": Capability("GIT_WRITE", CapabilityState.AVAILABLE, "Local git commit/branch operations permitted", ActionSafetyClass.WRITE),
        "SAFE_SHELL": Capability("SAFE_SHELL", CapabilityState.AVAILABLE, "Deterministic python/node test runners verified", ActionSafetyClass.READ),
        "WEB_RESEARCH": Capability("WEB_RESEARCH", CapabilityState.UNAVAILABLE, "No live unmetered search crawler active", ActionSafetyClass.READ),
        "BROWSER_READ": Capability("BROWSER_READ", CapabilityState.AVAILABLE, "Headless chrome CDP inspector verified", ActionSafetyClass.READ),
        "GITHUB_READ": Capability("GITHUB_READ", CapabilityState.AVAILABLE, "Local git tracking remote metadata verified", ActionSafetyClass.READ),
        "GITHUB_WRITE": Capability("GITHUB_WRITE", CapabilityState.APPROVAL_REQUIRED, "Remote repository write requires human approval", ActionSafetyClass.WRITE),
        "X_READ": Capability("X_READ", CapabilityState.AUTH_REQUIRED, "No X API token configured", ActionSafetyClass.READ),
        "X_WRITE": Capability("X_WRITE", CapabilityState.AUTH_REQUIRED, "No X API write token configured", ActionSafetyClass.PUBLISH),
        "YOUTUBE_READ": Capability("YOUTUBE_READ", CapabilityState.AUTH_REQUIRED, "No YouTube API token configured", ActionSafetyClass.READ),
        "YOUTUBE_PUBLISH": Capability("YOUTUBE_PUBLISH", CapabilityState.APPROVAL_REQUIRED, "Public video release requires human approval", ActionSafetyClass.PUBLISH),
        "TIKTOK_READ": Capability("TIKTOK_READ", CapabilityState.AUTH_REQUIRED, "No TikTok API token configured", ActionSafetyClass.READ),
        "TIKTOK_PUBLISH": Capability("TIKTOK_PUBLISH", CapabilityState.APPROVAL_REQUIRED, "Public short release requires human approval", ActionSafetyClass.PUBLISH),
        "EMAIL_READ": Capability("EMAIL_READ", CapabilityState.AUTH_REQUIRED, "No mailbox credential configured", ActionSafetyClass.READ),
        "EMAIL_SEND": Capability("EMAIL_SEND", CapabilityState.APPROVAL_REQUIRED, "External message dispatch requires human approval", ActionSafetyClass.WRITE),
        "CALENDAR_READ": Capability("CALENDAR_READ", CapabilityState.AUTH_REQUIRED, "No calendar token configured", ActionSafetyClass.READ),
        "CALENDAR_WRITE": Capability("CALENDAR_WRITE", CapabilityState.APPROVAL_REQUIRED, "Calendar mutation requires human approval", ActionSafetyClass.WRITE),
        "IMAGE_GENERATION": Capability("IMAGE_GENERATION", CapabilityState.UNAVAILABLE, "No local generative image pipeline active", ActionSafetyClass.WRITE),
        "VIDEO_PRODUCTION": Capability("VIDEO_PRODUCTION", CapabilityState.AVAILABLE, "Local Godot / FFmpeg video generation verified", ActionSafetyClass.WRITE),
    }

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.capabilities: dict[str, Capability] = dict(self.DEFAULT_CAPABILITIES)

    def get_capability(self, name: str) -> Capability:
        if name not in self.capabilities:
            return Capability(name, CapabilityState.UNAVAILABLE, f"Unknown capability '{name}' (fails closed)", ActionSafetyClass.READ)
        return self.capabilities[name]

    def is_available(self, name: str) -> bool:
        cap = self.get_capability(name)
        return cap.state == CapabilityState.AVAILABLE

    def export_summary(self) -> dict[str, str]:
        return {name: cap.state.value for name, cap in self.capabilities.items()}


# ============================================================================
# 3. PERSISTENT AGENT PROFILE & SECRET SANITIZATION
# ============================================================================

SECRET_PATTERNS = [
    re.compile(r"(?i)(password|passwd|pwd)"),
    re.compile(r"(?i)(secret|token|bearer|api[_-]?key|auth[_-]?code)"),
    re.compile(r"(?i)(private[_-]?key|ssh[_-]?key)"),
    re.compile(r"(?i)(credit[_-]?card|cvv|iban)"),
    re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b"),  # Base64 secret signature
]


def sanitize_profile_data(data: Any) -> Any:
    """Recursively validates and redacts any secret-like fields or keys."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            key_str = str(k).lower()
            if any(p.search(key_str) for p in SECRET_PATTERNS):
                raise ValueError(f"Security Invariant Violation: Secret field '{k}' is forbidden in persistent agent profiles")
            sanitized[k] = sanitize_profile_data(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_profile_data(item) for item in data]
    elif isinstance(data, str):
        for p in SECRET_PATTERNS:
            if p.search(data) and len(data) > 20 and not data.startswith("http") and not data.startswith("WF-") and not data.startswith("corr-"):
                return "[REDACTED_SECRET]"
        return data
    return data


@dataclass
class AgentProfile:
    agent_id: str
    name: str
    role: str
    capabilities: list[str]
    allowed_actions: list[str]
    approval_requirements: list[str]
    memory_scope: list[str]
    skills: list[str] = field(default_factory=list)
    routines: list[str] = field(default_factory=list)
    current_task: str | None = None
    last_task: str | None = None
    availability: str = "ONLINE"
    updated_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def __post_init__(self):
        # Validate against secret storage
        raw_dict = asdict(self)
        sanitize_profile_data(raw_dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentProfileRegistry:
    """Manages persistent, non-secret agent capability profiles."""

    DEFAULT_PROFILES = {
        "agent-chief-commander": AgentProfile(
            agent_id="agent-chief-commander",
            name="Chief Commander",
            role="Autonomous Orchestration & Review",
            capabilities=["LOCAL_FILES_READ", "LOCAL_FILES_WRITE", "GIT_READ", "SAFE_SHELL"],
            allowed_actions=["READ", "WRITE"],
            approval_requirements=["PUBLISH", "PAYMENT", "IDENTITY", "AUTH"],
            memory_scope=["strategy", "decisions", "policies"],
            skills=["REVIEW_BUDGET_EVALUATE", "CONTEXT_PACKAGE_BUILD"],
        ),
        "agent-courier-relay": AgentProfile(
            agent_id="agent-courier-relay",
            name="Courier Hub Relay",
            role="Physical Envelope Transport & Dispatch",
            capabilities=["LOCAL_FILES_READ", "LOCAL_FILES_WRITE", "SAFE_SHELL"],
            allowed_actions=["READ", "WRITE"],
            approval_requirements=["PUBLISH", "PAYMENT"],
            memory_scope=["transport", "dispatch_log"],
            skills=["COURIER_TASK_TRANSPORT", "COURIER_RESULT_TRANSPORT"],
        ),
        "smart-resource-router": AgentProfile(
            agent_id="smart-resource-router",
            name="Smart Resource Router",
            role="Workload Classification & Quota Protection",
            capabilities=["LOCAL_FILES_READ", "SAFE_SHELL"],
            allowed_actions=["READ"],
            approval_requirements=[],
            memory_scope=["resource_policies", "agent_specializations"],
            skills=[],
        ),
        "agent-antigravity-bridge": AgentProfile(
            agent_id="agent-antigravity-bridge",
            name="Antigravity Studio Bridge",
            role="Heavy Worker & 3D/Video Implementation",
            capabilities=["LOCAL_FILES_READ", "LOCAL_FILES_WRITE", "GIT_READ", "GIT_WRITE", "SAFE_SHELL", "VIDEO_PRODUCTION", "BROWSER_READ"],
            allowed_actions=["READ", "WRITE"],
            approval_requirements=["PUBLISH", "PAYMENT", "DELETE"],
            memory_scope=["render_pipelines", "studio_assets", "implementation"],
            skills=["LOCAL_CANARY_VERIFY"],
        ),
        "agent-codex-bridge": AgentProfile(
            agent_id="agent-codex-bridge",
            name="Codex Technical Lab",
            role="Independent Code Review & QA Specialist",
            capabilities=["LOCAL_FILES_READ", "GIT_READ", "SAFE_SHELL"],
            allowed_actions=["READ"],
            approval_requirements=["WRITE", "PUBLISH", "PAYMENT"],
            memory_scope=["code_reviews", "qa_audits", "syntax_rules"],
            skills=["REVIEW_BUDGET_EVALUATE"],
        ),
        "agent-thought-curator": AgentProfile(
            agent_id="agent-thought-curator",
            name="Thought Curator",
            role="Idea Ingestion & Memory Comparison",
            capabilities=["LOCAL_FILES_READ", "LOCAL_FILES_WRITE", "SAFE_SHELL"],
            allowed_actions=["READ", "WRITE"],
            approval_requirements=[],
            memory_scope=["raw_ideas", "curated_goals", "priorities"],
            skills=[],
        ),
        "agent-update-steward": AgentProfile(
            agent_id="agent-update-steward",
            name="Update Steward",
            role="Context Snapshotting & Invariant Auditing",
            capabilities=["LOCAL_FILES_READ", "LOCAL_FILES_WRITE", "GIT_READ"],
            allowed_actions=["READ", "WRITE"],
            approval_requirements=[],
            memory_scope=["context_snapshots", "diff_history"],
            skills=["CONTEXT_PACKAGE_BUILD"],
        ),
    }

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.profiles_dir = repo_dir / "events/agent-profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.profiles: dict[str, AgentProfile] = dict(self.DEFAULT_PROFILES)
        self._load_all()

    def _load_all(self):
        for p in self.profiles_dir.glob("*.json"):
            data = load_json(p)
            if data and isinstance(data, dict) and "agent_id" in data:
                try:
                    self.profiles[data["agent_id"]] = AgentProfile(**data)
                except Exception:
                    pass

    def get_profile(self, agent_id: str) -> AgentProfile | None:
        return self.profiles.get(agent_id)

    def list_profiles(self) -> list[AgentProfile]:
        return list(self.profiles.values())

    def save_profile(self, profile: AgentProfile) -> None:
        self.profiles[profile.agent_id] = profile
        target_path = self.profiles_dir / f"{profile.agent_id}.json"
        save_json(target_path, profile.to_dict())


# ============================================================================
# 4. SKILL REGISTRY (ONLY VERIFIED EXISTING WORKFLOWS)
# ============================================================================

class SkillLifecycle(str, enum.Enum):
    REGISTERED = "REGISTERED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DEPRECATED = "DEPRECATED"


@dataclass
class Skill:
    skill_id: str
    name: str
    version: str
    owner_agent: str
    description: str
    inputs: list[str]
    outputs: list[str]
    steps: list[str]
    required_capabilities: list[str]
    required_approvals: list[str]
    risk_level: str
    verification_state: SkillLifecycle = SkillLifecycle.ACTIVE
    last_verified: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    source: str = "VERIFIED_LOCAL_IMPLEMENTATION"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SkillRegistry:
    """Deterministic reusable Skill Registry grounded in verified local evidence."""

    INITIAL_VERIFIED_SKILLS: dict[str, Skill] = {
        "LOCAL_CANARY_VERIFY": Skill(
            skill_id="LOCAL_CANARY_VERIFY",
            name="Local Canary Roundtrip Verification",
            version="1.0.0",
            owner_agent="agent-antigravity-bridge",
            description="Reads local configuration fixtures and returns structured validation payload.",
            inputs=["task_instruction", "allowed_scope"],
            outputs=["result_payload", "payload_hash"],
            steps=["Parse instruction", "Inspect fixture: local_tools.json", "Format structured payload"],
            required_capabilities=["LOCAL_FILES_READ", "SAFE_SHELL"],
            required_approvals=[],
            risk_level="LOW",
        ),
        "REVIEW_BUDGET_EVALUATE": Skill(
            skill_id="REVIEW_BUDGET_EVALUATE",
            name="Review Budget & Risk Delta Evaluation",
            version="1.0.0",
            owner_agent="agent-codex-bridge",
            description="Computes changed diff hashes to determine whether independent model review is necessary.",
            inputs=["context_delta", "changed_files"],
            outputs=["review_decision", "risk_classification"],
            steps=["Load review policy", "Compute risk delta", "Determine model review need"],
            required_capabilities=["LOCAL_FILES_READ", "GIT_READ"],
            required_approvals=[],
            risk_level="LOW",
        ),
        "CONTEXT_PACKAGE_BUILD": Skill(
            skill_id="CONTEXT_PACKAGE_BUILD",
            name="Context Package & Snapshot Compilation",
            version="1.0.0",
            owner_agent="agent-update-steward",
            description="Builds cryptographically verifiable context snapshots and version tags.",
            inputs=["repo_directory", "context_delta"],
            outputs=["snapshot_current.json", "context_version"],
            steps=["Collect repository file hashes", "Build context snapshot", "Attach versioned delta"],
            required_capabilities=["LOCAL_FILES_READ", "LOCAL_FILES_WRITE"],
            required_approvals=[],
            risk_level="LOW",
        ),
        "COURIER_TASK_TRANSPORT": Skill(
            skill_id="COURIER_TASK_TRANSPORT",
            name="Courier Task Envelope Physical Transport",
            version="1.0.0",
            owner_agent="agent-courier-relay",
            description="Transports task envelopes from Chief Command to responsible worker desk via BFS routing.",
            inputs=["task_id", "target_agent"],
            outputs=["transport_state", "envelope_ack"],
            steps=["Acquire task envelope", "Transport to responsible worker desk", "Emit DISPATCHED state"],
            required_capabilities=["LOCAL_FILES_READ", "LOCAL_FILES_WRITE", "SAFE_SHELL"],
            required_approvals=[],
            risk_level="LOW",
        ),
        "COURIER_RESULT_TRANSPORT": Skill(
            skill_id="COURIER_RESULT_TRANSPORT",
            name="Courier Result Envelope Physical Transport",
            version="1.0.0",
            owner_agent="agent-courier-relay",
            description="Transports completed result envelopes from worker desk back to Chief Command.",
            inputs=["task_id", "result_file"],
            outputs=["chief_received_state", "result_ack"],
            steps=["Collect RESULT_READY from worker", "Transport to Chief Command", "Emit RESULT_RETURN state"],
            required_capabilities=["LOCAL_FILES_READ", "LOCAL_FILES_WRITE", "SAFE_SHELL"],
            required_approvals=[],
            risk_level="LOW",
        ),
    }

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.skills_dir = repo_dir / "events/skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.skills: dict[str, Skill] = dict(self.INITIAL_VERIFIED_SKILLS)

    def get_skill(self, skill_id: str) -> Skill | None:
        return self.skills.get(skill_id)

    def list_active_skills(self) -> list[Skill]:
        return [s for s in self.skills.values() if s.verification_state == SkillLifecycle.ACTIVE]


# ============================================================================
# 5. ROUTINE PROPOSAL SYSTEM
# ============================================================================

@dataclass
class RoutineProposal:
    proposal_id: str
    routine_name: str
    source_task_id: str
    source_correlation_id: str
    observed_steps: list[str]
    required_capabilities: list[str]
    required_approvals: list[str]
    risk_level: str
    redacted_fields: list[str]
    proposed_owner: str
    status: str = "PROPOSED"
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RoutineProposalSystem:
    """Extracts candidate routines from successful deterministic workflows without auto-approving."""

    @staticmethod
    def propose_routine_from_workflow(
        workflow_id: str,
        correlation_id: str,
        observed_steps: list[str],
        capabilities_used: list[str],
        owner_agent: str,
        risk_level: str = "LOW"
    ) -> RoutineProposal:
        # Sanitize observed steps for secrets
        clean_steps = []
        redacted = []
        for step in observed_steps:
            cleaned = sanitize_profile_data(step)
            if cleaned == "[REDACTED_SECRET]":
                redacted.append("step_payload")
                clean_steps.append("[REDACTED_DETERMINISTIC_STEP]")
            else:
                clean_steps.append(cleaned)

        proposal = RoutineProposal(
            proposal_id=f"prop-{uuid.uuid4().hex[:8]}",
            routine_name=f"routine-{workflow_id.lower()}",
            source_task_id=workflow_id,
            source_correlation_id=correlation_id,
            observed_steps=clean_steps,
            required_capabilities=capabilities_used,
            required_approvals=["CHIEF_APPROVAL_REQUIRED"],
            risk_level=risk_level,
            redacted_fields=redacted,
            proposed_owner=owner_agent,
            status="PROPOSED",
        )
        return proposal


# ============================================================================
# 6. AGENT-TO-AGENT HANDOFF PROTOCOL
# ============================================================================

@dataclass
class HandoffMessage:
    handoff_id: str
    from_agent: str
    to_agent: str
    task_id: str
    correlation_id: str
    reason: str
    context_manifest: dict[str, Any]
    required_capabilities: list[str]
    allowed_actions: list[str]
    expected_result: str
    approval_required: bool = False
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def __post_init__(self):
        if not self.task_id or not self.correlation_id:
            raise ValueError("Handoff Invariant Violation: task_id and correlation_id must be strictly preserved")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HandoffProtocol:
    """Manages deterministic task delegation between agents."""

    @staticmethod
    def create_handoff(
        from_agent: str,
        to_agent: str,
        task_id: str,
        correlation_id: str,
        reason: str,
        context_manifest: dict[str, Any],
        required_capabilities: list[str],
        expected_result: str,
        approval_required: bool = False
    ) -> HandoffMessage:
        return HandoffMessage(
            handoff_id=f"handoff-{uuid.uuid4().hex[:8]}",
            from_agent=from_agent,
            to_agent=to_agent,
            task_id=task_id,
            correlation_id=correlation_id,
            reason=reason,
            context_manifest=context_manifest,
            required_capabilities=required_capabilities,
            allowed_actions=["READ", "WRITE"],
            expected_result=expected_result,
            approval_required=approval_required,
        )


# ============================================================================
# 7. MINIMAL CONTEXT TRANSFER / DELTA ENGINE
# ============================================================================

class MinimalContextTransferEngine:
    """Enforces delta-only and hash-reference context transfers."""

    @staticmethod
    def transfer_context_minimal(
        task_id: str,
        correlation_id: str,
        current_snapshot: dict[str, Any],
        previous_snapshot: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        curr_hash = current_snapshot.get("snapshot_hash") or hashlib.sha256(json.dumps(current_snapshot, sort_keys=True).encode()).hexdigest()
        prev_hash = previous_snapshot.get("snapshot_hash") if previous_snapshot else None

        if prev_hash and curr_hash == prev_hash:
            # Hash unchanged: reference existing context (UNCHANGED_CONTEXT_RESEND = FORBIDDEN)
            return {
                "task_id": task_id,
                "correlation_id": correlation_id,
                "mode": "REFERENCE_EXISTING_CONTEXT",
                "snapshot_hash": curr_hash,
                "version": current_snapshot.get("version", 1),
                "delta": None,
            }

        # Context changed: compute delta only
        delta = {}
        if previous_snapshot:
            curr_files = current_snapshot.get("file_hashes", {})
            prev_files = previous_snapshot.get("file_hashes", {})
            changed_files = {k: v for k, v in curr_files.items() if prev_files.get(k) != v}
            delta["changed_files"] = changed_files
        else:
            delta["initial_state"] = True

        return {
            "task_id": task_id,
            "correlation_id": correlation_id,
            "mode": "SEND_DELTA_ONLY",
            "snapshot_hash": curr_hash,
            "version": current_snapshot.get("version", 1),
            "delta": delta,
        }


# ============================================================================
# 8. CONNECTOR REGISTRY
# ============================================================================

class ConnectorAuthState(str, enum.Enum):
    AUTHENTICATED = "AUTHENTICATED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"


@dataclass
class Connector:
    connector_id: str
    service: str
    capabilities: list[str]
    auth_state: ConnectorAuthState
    read_permissions: bool
    write_permissions: bool
    approval_policy: str
    quota_state: str
    last_verified: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConnectorRegistry:
    """Governs external connector metadata with fail-closed authentication states."""

    DEFAULT_CONNECTORS: dict[str, Connector] = {
        "connector-local-fs": Connector("connector-local-fs", "Local Filesystem", ["LOCAL_FILES_READ", "LOCAL_FILES_WRITE"], ConnectorAuthState.AUTHENTICATED, True, True, "POLICY_CONTROLLED", "UNLIMITED"),
        "connector-local-git": Connector("connector-local-git", "Local Git", ["GIT_READ", "GIT_WRITE"], ConnectorAuthState.AUTHENTICATED, True, True, "POLICY_CONTROLLED", "UNLIMITED"),
        "connector-github": Connector("connector-github", "GitHub", ["GITHUB_READ", "GITHUB_WRITE"], ConnectorAuthState.AUTH_REQUIRED, True, False, "HUMAN_GATE_FOR_WRITE", "UNKNOWN"),
        "connector-x": Connector("connector-x", "X", ["X_READ", "X_WRITE"], ConnectorAuthState.AUTH_REQUIRED, False, False, "HUMAN_GATE_ALWAYS", "UNKNOWN"),
        "connector-youtube": Connector("connector-youtube", "YouTube", ["YOUTUBE_READ", "YOUTUBE_PUBLISH"], ConnectorAuthState.AUTH_REQUIRED, False, False, "HUMAN_GATE_FOR_PUBLISH", "UNKNOWN"),
        "connector-tiktok": Connector("connector-tiktok", "TikTok", ["TIKTOK_READ", "TIKTOK_PUBLISH"], ConnectorAuthState.AUTH_REQUIRED, False, False, "HUMAN_GATE_FOR_PUBLISH", "UNKNOWN"),
        "connector-gmail": Connector("connector-gmail", "Gmail", ["EMAIL_READ", "EMAIL_SEND"], ConnectorAuthState.AUTH_REQUIRED, False, False, "HUMAN_GATE_FOR_SEND", "UNKNOWN"),
        "connector-calendar": Connector("connector-calendar", "Google Calendar", ["CALENDAR_READ", "CALENDAR_WRITE"], ConnectorAuthState.AUTH_REQUIRED, False, False, "HUMAN_GATE_FOR_WRITE", "UNKNOWN"),
    }

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.connectors: dict[str, Connector] = dict(self.DEFAULT_CONNECTORS)

    def get_connector(self, connector_id: str) -> Connector | None:
        return self.connectors.get(connector_id)

    def export_summary(self) -> dict[str, dict]:
        return {cid: conn.to_dict() for cid, conn in self.connectors.items()}


# ============================================================================
# 9. RESUMABLE HUMAN GATE MANAGER
# ============================================================================

import hmac
import hashlib
import sqlite3
import datetime
from pathlib import Path
import os
import uuid
from typing import Any

import hmac
import hashlib
import sqlite3
import datetime
from pathlib import Path
import os
import uuid
from typing import Any

class ResumableHumanGateManager:
    """Handles human takeover gates while strictly preserving workflow identity."""
    
    SUPPORTED_GATES = {
        "LOGIN", "OAUTH", "2FA", "CAPTCHA", "PAYMENT", "PURCHASE",
        "PUBLICATION", "LEGAL", "IDENTITY", "DESTRUCTIVE_ACTION", "PERMISSION_ESCALATION"
    }
    
    @staticmethod
    def _owner_secret() -> bytes:
        """Authority is injected by the owner; it must never be embedded in source."""
        secret = os.environ.get("COURIER_HUMAN_GATE_SECRET")
        if not secret or len(secret) < 32:
            raise PermissionError("HUMAN_GATE_OWNER_AUTHORITY_UNAVAILABLE")
        return secret.encode("utf-8")
    
    @staticmethod
    def _get_ledger_path():
        root = Path(os.environ.get("COURIER_REPO_ROOT", ".")).resolve()
        p = root / ".courier_state" / "human_gates.db"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def init_ledger():
        conn = sqlite3.connect(ResumableHumanGateManager._get_ledger_path())
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS consumed_approvals (gate_id TEXT PRIMARY KEY, consumed_at REAL)")
        conn.commit()
        conn.close()

    @staticmethod
    def trigger_gate(gate_type: str, workflow_id: str, correlation_id: str, task_id: str, reason: str) -> dict[str, Any]:
        if gate_type not in ResumableHumanGateManager.SUPPORTED_GATES:
            raise ValueError(f"Unsupported gate type '{gate_type}'")
        return {
            "gate_id": f"gate-{uuid.uuid4().hex[:8]}",
            "gate_type": gate_type,
            "status": "BLOCKED_HUMAN_GATE",
            "resumable": True,
            "workflow_id": workflow_id,
            "correlation_id": correlation_id,
            "task_id": task_id,
            "reason": reason,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        
    @staticmethod
    def issue_approval(gate_id: str, task_id: str, correlation_id: str, decision: str, issuer: str) -> dict[str, Any]:
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        payload = f"{gate_id}:{task_id}:{correlation_id}:{decision}:{issuer}:{timestamp}"
        signature = hmac.new(ResumableHumanGateManager._owner_secret(), payload.encode(), hashlib.sha256).hexdigest()
        return {
            "gate_id": gate_id,
            "task_id": task_id,
            "correlation_id": correlation_id,
            "decision": decision,
            "issuer": issuer,
            "timestamp": timestamp,
            "signature": signature
        }

    @staticmethod
    def resume_after_gate(gate_payload: dict[str, Any], approval: dict[str, Any] = None) -> dict[str, Any]:
        if not approval:
            raise ValueError("Direct bypass attempted without approval proof")
            
        payload = f"{approval['gate_id']}:{approval['task_id']}:{approval['correlation_id']}:{approval['decision']}:{approval['issuer']}:{approval['timestamp']}"
        expected = hmac.new(ResumableHumanGateManager._owner_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, approval.get('signature', '')):
            raise ValueError("Forged or invalid approval signature")
            
        if approval['decision'] != "APPROVE":
            raise ValueError("Approval decision is not APPROVE")
            
        if approval['issuer'] != "HUMAN":
            raise ValueError("Issuer must be HUMAN")
            
        if approval['gate_id'] != gate_payload['gate_id']:
            raise ValueError("Approval bound to wrong gate_id")
            
        if approval['task_id'] != gate_payload['task_id']:
            raise ValueError("Approval bound to wrong task_id")
            
        if approval['correlation_id'] != gate_payload['correlation_id']:
            raise ValueError("Approval bound to wrong correlation_id")
            
        # Check freshness
        app_time = datetime.datetime.fromisoformat(approval['timestamp'])
        now = datetime.datetime.now(datetime.timezone.utc)
        age_seconds = (now - app_time).total_seconds()
        if age_seconds < 0 or age_seconds > 86400: # future timestamps fail closed too
            raise ValueError("Approval is stale/expired")
            
        ResumableHumanGateManager.init_ledger()
        conn = sqlite3.connect(ResumableHumanGateManager._get_ledger_path(), isolation_level=None)
        c = conn.cursor()
        try:
            c.execute("BEGIN IMMEDIATE")
            c.execute("INSERT INTO consumed_approvals (gate_id, consumed_at) VALUES (?, ?)", 
                      (approval['gate_id'], datetime.datetime.now().timestamp()))
            c.execute("COMMIT")
        except sqlite3.IntegrityError:
            c.execute("ROLLBACK")
            conn.close()
            raise ValueError("Approval already consumed")
        conn.close()

        return {
            "workflow_id": gate_payload["workflow_id"],
            "correlation_id": gate_payload["correlation_id"],
            "task_id": gate_payload["task_id"],
            "status": "RESUMED",
            "gate_cleared": gate_payload["gate_id"],
            "resumed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
