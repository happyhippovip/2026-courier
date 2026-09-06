"""Durable Experience Engine & Organizational Memory (Mission 225-R1).

Records experiments, actions, expected vs actual results, costs, revenues,
failures, successes, lessons, and reusable patterns.

Rules:
- NO SECRET DATA.
- Explicit EVIDENCE_TYPE: SIMULATED, OBSERVED, EXTERNAL_TEST, REAL_REVENUE_VERIFIED.
- Simulation tests MUST NOT record 'customer demand verified' or pretend real revenue arrived.
- Experiences are persisted atomically to events/opportunity-os/experiences/
"""

from __future__ import annotations

import enum
import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional


class ExperienceEvidenceType(enum.Enum):
    SIMULATED = "SIMULATED"
    OBSERVED = "OBSERVED"
    EXTERNAL_TEST = "EXTERNAL_TEST"
    REAL_REVENUE_VERIFIED = "REAL_REVENUE_VERIFIED"


@dataclass
class ExperienceRecord:
    experience_id: str
    opportunity_id: str
    domain: str
    hypothesis: str
    evidence_before: List[str]
    action_taken: str
    expected_result: str
    actual_result: str
    cost_eur: float
    revenue_eur: float
    time_used_hours: float
    success: bool
    evidence_type: ExperienceEvidenceType = ExperienceEvidenceType.SIMULATED
    failure_mode: Optional[str] = None
    lesson: str = ""
    confidence_delta: float = 0.0
    reusable_pattern: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        # Strict validation: Never claim verified customer demand or revenue if evidence_type is SIMULATED
        if self.evidence_type == ExperienceEvidenceType.SIMULATED:
            lesson_lower = self.lesson.lower()
            actual_lower = self.actual_result.lower()
            if "customer demand" in lesson_lower or "verified demand" in lesson_lower:
                if self.revenue_eur == 0.0:
                    raise ValueError("SIMULATED experience cannot claim customer demand or verified demand without external test.")
            if "customer demand" in actual_lower or "verified demand" in actual_lower:
                if self.revenue_eur == 0.0:
                    raise ValueError("SIMULATED experience cannot claim customer demand or verified demand in actual_result.")

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["evidence_type"] = self.evidence_type.value
        d["timestamp"] = self.timestamp.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExperienceRecord:
        data_copy = dict(data)
        if isinstance(data_copy.get("timestamp"), str):
            data_copy["timestamp"] = datetime.fromisoformat(data_copy["timestamp"])
        if isinstance(data_copy.get("evidence_type"), str):
            data_copy["evidence_type"] = ExperienceEvidenceType(data_copy["evidence_type"])
        elif "evidence_type" not in data_copy:
            data_copy["evidence_type"] = ExperienceEvidenceType.SIMULATED
        return cls(**data_copy)


class ExperienceEngine:
    DEFAULT_STORAGE_DIR = "events/opportunity-os/experiences"

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or os.path.join(os.getcwd(), self.DEFAULT_STORAGE_DIR))
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def record_experience(self, exp: ExperienceRecord) -> str:
        """Atomically persists an ExperienceRecord to disk."""
        filename = f"{exp.experience_id}.json"
        path = self.storage_dir / filename
        tmp_path = self.storage_dir / f"{filename}.tmp.{uuid.uuid4().hex}"

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(exp.to_dict(), f, indent=2)
        os.replace(tmp_path, path)
        return str(path)

    def query_lessons(self, domain: Optional[str] = None, keyword: Optional[str] = None) -> List[ExperienceRecord]:
        """Retrieves past experience records matching domain or keywords."""
        results = []
        if not self.storage_dir.exists():
            return results

        for p in self.storage_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                exp = ExperienceRecord.from_dict(data)
                
                if domain and exp.domain != domain:
                    continue
                if keyword:
                    kw_lower = keyword.lower()
                    text_blob = f"{exp.hypothesis} {exp.action_taken} {exp.lesson} {exp.reusable_pattern}".lower()
                    if kw_lower not in text_blob:
                        continue
                results.append(exp)
            except Exception:
                continue

        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results

    def check_precedents_before_proposal(self, domain: str, action_concept: str) -> Dict[str, Any]:
        """Advises whether similar actions previously succeeded or failed."""
        matches = self.query_lessons(domain=domain, keyword=action_concept)
        if not matches:
            return {
                "has_precedent": False,
                "recommendation": "PROCEED_WITH_CHEAP_TEST",
                "relevant_failures": 0,
                "reusable_patterns": []
            }

        failures = [m for m in matches if not m.success]
        successes = [m for m in matches if m.success]
        reusable = [m.reusable_pattern for m in matches if m.reusable_pattern]
        
        return {
            "has_precedent": True,
            "success_count": len(successes),
            "failure_count": len(failures),
            "warnings": [f.lesson for f in failures],
            "reusable_patterns": reusable,
            "recommendation": "CAUTION_CHECK_PAST_FAILURES" if len(failures) > len(successes) else "APPLY_PAST_PATTERNS"
        }
