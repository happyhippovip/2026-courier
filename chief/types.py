"""
Courier Chief Types & Data Models
Canonical definitions for the Local Chief Ingestion + Delta Coordination Layer.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class Lane(Enum):
    WINDOWS_CLI_1 = "WINDOWS_CLI_1"
    WINDOWS_CLI_2 = "WINDOWS_CLI_2"
    WINDOWS_GOOGLE = "WINDOWS_GOOGLE"
    MAC_GOOGLE = "MAC_GOOGLE"
    CODEX = "CODEX"
    CHIEF = "CHIEF"
    HUMAN = "HUMAN"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_str(cls, s: str) -> "Lane":
        s_clean = s.strip().upper().replace("-", "_")
        for member in cls:
            if member.value == s_clean or member.name == s_clean:
                return member
        return cls.UNKNOWN


class Host(Enum):
    WINDOWS = "WINDOWS"
    MAC = "MAC"
    REMOTE = "REMOTE"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_str(cls, s: str) -> "Host":
        s_clean = s.strip().upper()
        if "WIN" in s_clean:
            return cls.WINDOWS
        elif "MAC" in s_clean or "DARWIN" in s_clean:
            return cls.MAC
        elif "REMOTE" in s_clean or "CLOUD" in s_clean:
            return cls.REMOTE
        return cls.UNKNOWN


class TaskStatus(Enum):
    PENDING = "PENDING"
    READY = "READY"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    RESULT_READY = "RESULT_READY"
    VERIFIED = "VERIFIED"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"



class FindingStatus(Enum):
    REPORTED = "REPORTED"
    CONFIRMED = "CONFIRMED"
    RETRACTED = "RETRACTED"
    WRONG_SCOPE = "WRONG_SCOPE"


class FindingSeverity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class PatchStatus(Enum):
    PROPOSED = "PROPOSED"
    VERIFIED_LOCAL = "VERIFIED_LOCAL"
    STAGED_FOR_MAC = "STAGED_FOR_MAC"
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"


class AuthorityTier(Enum):
    TIER_1_PHYSICAL = 1
    TIER_2_CANONICAL_SQLITE = 2
    TIER_3_IMMUTABLE_CRYPTO = 3
    TIER_4_CIRCUIT_BREAKER = 4
    TIER_5_IN_MEMORY = 5
    TIER_6_LEGACY_PROMPT = 6


@dataclass
class TwoLevelDone:
    local_step_erledigt: bool
    gesamtaufgabe_erledigt: bool
    blocker: str = "NONE"
    next_step: str = ""

    def validate_invariants(self) -> bool:
        """
        Strict Invariant:
        If blocker is not NONE, gesamtaufgabe_erledigt MUST be False.
        """
        if self.blocker != "NONE" and self.blocker != "" and self.gesamtaufgabe_erledigt:
            return False
        return True


@dataclass
class IngestedHandoff:
    handoff_id: str
    source_file: str
    origin_lane: Lane
    assignment_id: str
    role: str
    timestamp_utc: str
    host_os: Host
    mac_host_access: bool
    production_write_authority: bool
    sha256_hash: str
    raw_payload: Dict[str, Any]
    ingested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    validation_status: str = "VERIFIED"
    validation_errors: List[str] = field(default_factory=list)


@dataclass
class RegisteredFinding:
    finding_id: str
    origin_lane: Lane
    title: str
    status: FindingStatus
    severity: FindingSeverity
    description: str
    reproduction_ref: Optional[str] = None
    evidence_hash: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class RegisteredPatch:
    patch_id: str
    batch_name: str
    status: PatchStatus
    description: str
    target_files: List[str] = field(default_factory=list)
    reproduction_scripts: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DispatchEnvelope:
    dispatch_id: str
    target_lane: Lane
    target_host: Host
    assignment_id: str
    source_lane: Lane = Lane.WINDOWS_CLI_1
    prompt_text: str = ""
    required_inputs: List[str] = field(default_factory=list)
    output_contract: Dict[str, Any] = field(default_factory=dict)
    single_writer_resource: Optional[str] = None
    status: str = "STAGED"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
