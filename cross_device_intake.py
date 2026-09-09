"""
Courier Cross-Device Task Intake & Team Coordination Engine
One Company Model: Mac + Windows = One Organization / One Project / One Team
Durable coordination engine for routing inputs between Windows, macOS, Gemini, Codex, CLI1, Chief.
"""

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Optional, Dict, Any, List

class Host(Enum):
    MAC = "MAC"
    WINDOWS = "WINDOWS"
    REMOTE = "REMOTE"
    UNKNOWN = "UNKNOWN"

class Agent(Enum):
    GEMINI = "GEMINI"
    CLI1 = "CLI1"
    CODEX = "CODEX"
    CHIEF = "CHIEF"
    UNKNOWN = "UNKNOWN"

class MessageClass(Enum):
    STATUS_ONLY = "STATUS_ONLY"
    TASK_REQUEST = "TASK_REQUEST"
    HUMAN_GATE = "HUMAN_GATE"
    BLOCKER_REPORT = "BLOCKER_REPORT"
    DELEGATION_TO_CHIEF = "DELEGATION_TO_CHIEF"
    COMPLETED_RESULT = "COMPLETED_RESULT"

class TaskStatus(Enum):
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    DONE = "DONE"
    PARTIAL = "PARTIAL"

class ActionDomain(Enum):
    CONNECTED_REMOTE = "CONNECTED_REMOTE"
    LOCAL_MACHINE = "LOCAL_MACHINE"
    HUMAN_ONLY = "HUMAN_ONLY"

@dataclass
class IntakeResult:
    message_class: MessageClass
    task_description: str
    status: TaskStatus
    erledigt: bool
    evidence: str
    blocker: str
    next_step: str
    action_domain: ActionDomain
    requires_worker_launch: bool = False
    agent: Agent = Agent.UNKNOWN
    host: Host = Host.UNKNOWN
    local_step_erledigt: bool = False
    gesamtaufgabe_erledigt: bool = False

    def to_terminal_format(self) -> str:
        return (
            f"AUFGABE: {self.task_description}\n"
            f"STATUS: {self.status.value}\n"
            f"ERLEDIGT: {'JA' if self.erledigt else 'NEIN'}\n"
            f"LOCAL_STEP_ERLEDIGT: {'JA' if self.local_step_erledigt else 'NEIN'}\n"
            f"GESAMTAUFGABE_ERLEDIGT: {'JA' if self.gesamtaufgabe_erledigt else 'NEIN'}\n"
            f"BEWEIS: {self.evidence}\n"
            f"BLOCKER: {self.blocker}\n"
            f"NÄCHSTER_SCHRITT: {self.next_step}"
        )

def detect_host_and_agent(text: str) -> tuple[Host, Agent]:
    """
    Discovers HOST and AGENT from evidence without guessing.
    Agent (capability) and Host (environment) remain strictly distinct.
    """
    t_lower = text.lower()

    # 1. Agent Detection
    agent = Agent.UNKNOWN
    if 'gemini' in t_lower or 'antigravity' in t_lower:
        agent = Agent.GEMINI
    elif 'cli1' in t_lower:
        agent = Agent.CLI1
    elif 'codex' in t_lower:
        agent = Agent.CODEX
    elif 'chief' in t_lower or 'chatgpt' in t_lower:
        agent = Agent.CHIEF

    # 2. Host Detection from path/environment evidence
    host = Host.UNKNOWN
    # Windows path evidence: e.g. C:\Users\... or drive letter with backslash
    if re.search(r'[a-zA-Z]:\\[^\s]+|[a-zA-Z]:/[^\s]+|c:\\users\\lol', t_lower):
        host = Host.WINDOWS
    # Mac path evidence: e.g. /Users/... or POSIX /private/...
    elif re.search(r'/users/[^\s]+|/private/var/[^\s]+', t_lower):
        host = Host.MAC
    # Connected remote evidence
    elif 'github connector' in t_lower or 'remote github' in t_lower:
        host = Host.REMOTE

    # Invariant: Never infer GOOGLE=WINDOWS or GOOGLE=MAC.
    return host, agent

class CrossMachineResourceManager:
    """
    Enforces cross-machine SINGLE_WRITER = YES across the organization.
    Concurrent writes to the same repository/resource are serialized.
    Independent read-only tasks may run concurrently.
    """
    def __init__(self):
        # resource_key -> { active_writer_host, active_writer_agent, is_write }
        self.active_resources: Dict[str, Dict[str, Any]] = {}

    def request_access(self, resource_id: str, host: Host, is_write: bool = True) -> tuple[bool, str]:
        if not is_write:
            return True, "READ_ONLY_ALLOWED"

        current = self.active_resources.get(resource_id)
        if current and current.get('is_write', False):
            active_host = current.get('host')
            if active_host != host:
                return False, f"SINGLE_WRITER_CONFLICT: Active writer on {active_host.value} holds write lock on {resource_id}"

        # Grant lock
        self.active_resources[resource_id] = {'host': host, 'is_write': is_write}
        return True, "WRITE_LOCK_ACQUIRED"

    def release_access(self, resource_id: str):
        if resource_id in self.active_resources:
            del self.active_resources[resource_id]

class CrossDeviceIntakeEngine:
    def __init__(self):
        self.resource_manager = CrossMachineResourceManager()
        self.human_gate_patterns = [
            r'oauth', r'login n[öo]tig', r'auth login', r'2fa', r'password',
            r'passwort', r'credential', r'keychain', r'human_gate', r'blocked by oauth'
        ]
        self.delegation_patterns = [
            r'chatgpt soll', r'chief soll', r'über den verbundenen github',
            r'delegat', r'mach du das', r'übernimm das', r'kurier das'
        ]
        self.verified_evidence_patterns = [
            r'pass', r'erfolgreich', r'verifiziert', r'100%', r'bit-for-bit',
            r'commit [0-9a-f]{7}', r'sha-256'
        ]

    def classify_and_route(self, text: str, context: Optional[Dict[str, Any]] = None) -> IntakeResult:
        t = text.strip()
        t_lower = t.lower()
        ctx = context or {}

        host, agent = detect_host_and_agent(text)

        # 1. Check for Human Gate
        is_human_gate = any(re.search(pat, t_lower) for pat in self.human_gate_patterns)
        if is_human_gate and not ctx.get('authenticated', False):
            local_step_done = ctx.get('local_step_done', False)
            return IntakeResult(
                message_class=MessageClass.HUMAN_GATE,
                task_description=f"Human authorization gate required ({t})",
                status=TaskStatus.BLOCKED,
                erledigt=False,
                evidence="Authentication barrier encountered; local human agency required",
                blocker=t,
                next_step="Human must perform one-time authentication action",
                action_domain=ActionDomain.HUMAN_ONLY,
                requires_worker_launch=False,
                agent=agent,
                host=host,
                local_step_erledigt=local_step_done,
                gesamtaufgabe_erledigt=False
            )

        # 2. Check for Delegation to Chief / Connected Action
        is_delegation = any(re.search(pat, t_lower) for pat in self.delegation_patterns)
        if is_delegation:
            # Check if task asks to push local bytes existing only on local machine
            requires_local_bytes = ctx.get('requires_local_bytes', False) or 'unpushed' in t_lower or 'local commit' in t_lower
            if requires_local_bytes:
                return IntakeResult(
                    message_class=MessageClass.TASK_REQUEST,
                    task_description=f"Local machine task required: {t}",
                    status=TaskStatus.RUNNING,
                    erledigt=False,
                    evidence="Unpushed bytes exist exclusively on local machine; Chief cannot access them remotely",
                    blocker="Local bytes not available to Chief",
                    next_step="Route local operation to machine-local agent",
                    action_domain=ActionDomain.LOCAL_MACHINE,
                    requires_worker_launch=True,
                    agent=agent,
                    host=host,
                    local_step_erledigt=False,
                    gesamtaufgabe_erledigt=False
                )

            has_connected_tool = ctx.get('has_connected_tool', True)
            if has_connected_tool:
                return IntakeResult(
                    message_class=MessageClass.DELEGATION_TO_CHIEF,
                    task_description=f"Execute connected action on Chief ({t})",
                    status=TaskStatus.RUNNING,
                    erledigt=False,
                    evidence="Connected tool capability available in Chief environment",
                    blocker="NONE",
                    next_step="Chief executes task via connected tool",
                    action_domain=ActionDomain.CONNECTED_REMOTE,
                    requires_worker_launch=True,
                    agent=agent,
                    host=host,
                    local_step_erledigt=False,
                    gesamtaufgabe_erledigt=False
                )

        # 3. Check for Partial Status
        if 'partial' in t_lower or 'teilweise' in t_lower or 'unvollständig' in t_lower:
            return IntakeResult(
                message_class=MessageClass.BLOCKER_REPORT,
                task_description=f"Partial progress reported ({t})",
                status=TaskStatus.PARTIAL,
                erledigt=False,
                evidence=t,
                blocker="Required sub-steps remain incomplete",
                next_step="Complete remaining steps before marking done",
                action_domain=ActionDomain.LOCAL_MACHINE,
                requires_worker_launch=True,
                agent=agent,
                host=host,
                local_step_erledigt=True,
                gesamtaufgabe_erledigt=False
            )

        # 4. Check for In-Progress
        if 'running' in t_lower or 'läuft' in t_lower or 'still running' in t_lower:
            return IntakeResult(
                message_class=MessageClass.STATUS_ONLY,
                task_description=f"Background task in progress ({t})",
                status=TaskStatus.RUNNING,
                erledigt=False,
                evidence=t,
                blocker="NONE",
                next_step="Wait for running worker to finish; do not spawn duplicate",
                action_domain=ActionDomain.LOCAL_MACHINE,
                requires_worker_launch=False,
                agent=agent,
                host=host,
                local_step_erledigt=False,
                gesamtaufgabe_erledigt=False
            )

        # 5. Check for Continuation Directive ("weiter")
        if t_lower == 'weiter' or t_lower == 'continue':
            return IntakeResult(
                message_class=MessageClass.TASK_REQUEST,
                task_description="Execute single next safe local task",
                status=TaskStatus.RUNNING,
                erledigt=False,
                evidence="Explicit user continuation directive received",
                blocker="NONE",
                next_step="Execute exactly ONE next safe local action",
                action_domain=ActionDomain.LOCAL_MACHINE,
                requires_worker_launch=True,
                agent=agent,
                host=host,
                local_step_erledigt=False,
                gesamtaufgabe_erledigt=False
            )

        # 6. Check for Worker Claims vs. Genuine Evidence
        has_evidence = any(re.search(pat, t_lower) for pat in self.verified_evidence_patterns)
        worker_claim_only = ('worker says' in t_lower or 'erfolgreich behauptet' in t_lower or 'claims success' in t_lower) and not has_evidence

        if worker_claim_only:
            return IntakeResult(
                message_class=MessageClass.STATUS_ONLY,
                task_description=f"Unverified worker claim: {t}",
                status=TaskStatus.BLOCKED,
                erledigt=False,
                evidence="Worker claim lacks independent verification or effect proof",
                blocker="Unverified claim; effect not proven",
                next_step="Execute deterministic verification test to confirm claim",
                action_domain=ActionDomain.LOCAL_MACHINE,
                requires_worker_launch=False,
                agent=agent,
                host=host,
                local_step_erledigt=False,
                gesamtaufgabe_erledigt=False
            )

        # 7. Check for Completed Result backed by Evidence
        if has_evidence and not ('error' in t_lower or 'fail' in t_lower or 'blocked' in t_lower):
            return IntakeResult(
                message_class=MessageClass.COMPLETED_RESULT,
                task_description=f"Verified result: {t}",
                status=TaskStatus.DONE,
                erledigt=True,
                evidence=t,
                blocker="NONE",
                next_step="NONE",
                action_domain=ActionDomain.LOCAL_MACHINE,
                requires_worker_launch=False,
                agent=agent,
                host=host,
                local_step_erledigt=True,
                gesamtaufgabe_erledigt=True
            )

        # 8. Default fallback
        return IntakeResult(
            message_class=MessageClass.STATUS_ONLY,
            task_description=t,
            status=TaskStatus.PARTIAL,
            erledigt=False,
            evidence=t,
            blocker="NONE",
            next_step="Inspect status and define next action",
            action_domain=ActionDomain.LOCAL_MACHINE,
            requires_worker_launch=False,
            agent=agent,
            host=host,
            local_step_erledigt=False,
            gesamtaufgabe_erledigt=False
        )
