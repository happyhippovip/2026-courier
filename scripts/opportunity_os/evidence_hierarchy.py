"""Evidence Hierarchy & Social Signal Policy (Mission 225).

Defines evidence levels from Level A (audited primary data) down to
Level E (social likes/views/followers).

Rule: Level E has QUALITY_WEIGHT = 0.0 and may NEVER independently authorize action.
Social signals are collected strictly as manipulation/crowding/marketing risk signals.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


class EvidenceLevel(enum.Enum):
    LEVEL_A = "LEVEL_A"  # primary/official records, contracts, official fees, audited statements, first-party APIs
    LEVEL_B = "LEVEL_B"  # independent reputable sources, historical execution data, documented customer demand, actual orders
    LEVEL_C = "LEVEL_C"  # reputable specialist analysis, industry reports
    LEVEL_D = "LEVEL_D"  # community discussions/reviews
    LEVEL_E = "LEVEL_E"  # social likes/views/follower count (HYPE)


EVIDENCE_WEIGHTS = {
    EvidenceLevel.LEVEL_A: 1.0,
    EvidenceLevel.LEVEL_B: 0.8,
    EvidenceLevel.LEVEL_C: 0.5,
    EvidenceLevel.LEVEL_D: 0.2,
    EvidenceLevel.LEVEL_E: 0.0,  # Strict: 0 weight in opportunity quality
}


@dataclass
class EvidenceItem:
    evidence_id: str
    level: EvidenceLevel
    source_name: str
    description: str
    verified: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_reference: Optional[str] = None

    @property
    def quality_weight(self) -> float:
        return EVIDENCE_WEIGHTS.get(self.level, 0.0)


@dataclass
class SocialSignalAnalysis:
    likes: int = 0
    views: int = 0
    reposts: int = 0
    follower_count: int = 0
    sentiment_score: float = 0.0
    crowding_risk: float = 0.0
    manipulation_risk: float = 0.0
    is_viral: bool = False

    def get_quality_evidence_weight(self) -> float:
        """Enforces: Social signals have exactly 0 quality weight."""
        return 0.0

    def assess_risk(self) -> str:
        """Social metrics serve as marketing/crowding/manipulation risk indicators only."""
        if self.likes > 100000 and self.follower_count < 1000:
            self.manipulation_risk = 0.9
            return "HIGH_MANIPULATION_RISK"
        if self.views > 500000:
            self.crowding_risk = 0.8
            return "HIGH_CROWDING_RISK"
        return "NORMAL_OBSERVATION"


class EvidenceEvaluator:
    @staticmethod
    def calculate_evidence_score(items: List[EvidenceItem]) -> float:
        """Deterministic calculation of combined evidence confidence.
        
        LEVEL_E items contribute 0 to the quality score.
        """
        if not items:
            return 0.0
        
        # Filter out level E for quality authorization
        valid_items = [item for item in items if item.level != EvidenceLevel.LEVEL_E and item.verified]
        if not valid_items:
            return 0.0

        total_weight = sum(item.quality_weight for item in valid_items)
        # Scaled score bounded to [0.0, 1.0]
        return min(1.0, total_weight / 3.0)

    @staticmethod
    def can_authorize_action(items: List[EvidenceItem]) -> bool:
        """Level E alone can NEVER authorize an action.
        Requires at least one verified Level A or Level B item,
        or multiple verified Level C items.
        """
        has_level_a_or_b = any(item.verified and item.level in [EvidenceLevel.LEVEL_A, EvidenceLevel.LEVEL_B] for item in items)
        level_c_count = sum(1 for item in items if item.verified and item.level == EvidenceLevel.LEVEL_C)
        return has_level_a_or_b or (level_c_count >= 2)
