from __future__ import annotations
import enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class NewsSource(enum.Enum):
    CENTRAL_BANK = 'CENTRAL_BANK'
    ECONOMIC_RELEASE = 'ECONOMIC_RELEASE'
    REGULATORY = 'REGULATORY'
    EXCHANGE_OUTAGE = 'EXCHANGE_OUTAGE'
    ETF_FLOW = 'ETF_FLOW'
    SECURITY_EVENT = 'SECURITY_EVENT'
    INSOLVENCY = 'INSOLVENCY'
    GEOPOLITICAL = 'GEOPOLITICAL'
    EIA_PETROLEUM = 'EIA_PETROLEUM'
    EIA_NATGAS = 'EIA_NATGAS'
    OPEC = 'OPEC'
    SHIPPING_DISRUPTION = 'SHIPPING_DISRUPTION'
    REFINERY_OUTAGE = 'REFINERY_OUTAGE'
    PIPELINE_OUTAGE = 'PIPELINE_OUTAGE'
    SOCIAL_MEDIA = 'SOCIAL_MEDIA'
    UNKNOWN = 'UNKNOWN'

class VerificationState(enum.Enum):
    UNVERIFIED = 'UNVERIFIED'
    SINGLE_SOURCE = 'SINGLE_SOURCE'
    MULTI_SOURCE_VERIFIED = 'MULTI_SOURCE_VERIFIED'
    DEBUNKED = 'DEBUNKED'

@dataclass
class NewsEvent:
    event_id: str
    headline: str
    source_type: NewsSource
    verification_state: VerificationState
    sources_count: int
    timestamp: datetime
    instrument_relevance: List[str]
    impact_class: str
    is_scheduled_release: bool

@dataclass
class VerificationResult:
    state: VerificationState
    message: str

@dataclass
class OilReleaseFreezeWindow:
    release_name: str
    scheduled_time: datetime
    pre_freeze_minutes: int = 30
    post_stabilization_minutes: int = 15

@dataclass
class FreezeResult:
    frozen: bool
    reason: str
    window_name: str
    resumes_at: Optional[datetime]

@dataclass
class SuspicionResult:
    suspicion_score: float
    reasons: List[str]

class NewsDefense:
    def verify_event(self, event: NewsEvent) -> VerificationResult:
        if event.verification_state == VerificationState.DEBUNKED:
            return VerificationResult(VerificationState.DEBUNKED, "Event is debunked.")
        
        if event.sources_count >= 2:
            event.verification_state = VerificationState.MULTI_SOURCE_VERIFIED
            return VerificationResult(VerificationState.MULTI_SOURCE_VERIFIED, "Verified by multiple sources.")
        elif event.sources_count == 1:
            event.verification_state = VerificationState.SINGLE_SOURCE
            return VerificationResult(VerificationState.SINGLE_SOURCE, "Single source only.")
            
        event.verification_state = VerificationState.UNVERIFIED
        return VerificationResult(VerificationState.UNVERIFIED, "No sources verified.")

    def can_trigger_trade(self, event: NewsEvent) -> bool:
        if event.verification_state == VerificationState.UNVERIFIED:
            return False
        if event.verification_state == VerificationState.SINGLE_SOURCE and event.source_type == NewsSource.SOCIAL_MEDIA:
            return False
        if event.verification_state == VerificationState.DEBUNKED:
            return False
        return True

    def is_in_freeze_window(self, now: datetime, windows: List[OilReleaseFreezeWindow]) -> FreezeResult:
        for window in windows:
            freeze_start = window.scheduled_time - timedelta(minutes=window.pre_freeze_minutes)
            freeze_end = window.scheduled_time + timedelta(minutes=window.post_stabilization_minutes)
            if freeze_start <= now <= freeze_end:
                return FreezeResult(
                    frozen=True,
                    reason="Within freeze window.",
                    window_name=window.release_name,
                    resumes_at=freeze_end
                )
        return FreezeResult(False, "", "", None)

    def detect_suspicious_headline(self, headline: str, claimed_source: str) -> SuspicionResult:
        reasons = []
        score = 0.0
        
        headline_lower = headline.lower()
        if 'repost' in headline_lower or 'breaking:' in headline_lower:
            reasons.append("Contains potential repost or old-headline pattern")
            score += 0.5
            
        if claimed_source == 'SOCIAL_MEDIA' or claimed_source == NewsSource.SOCIAL_MEDIA.value:
            reasons.append("Single unverified social media source proxy")
            score += 0.4
            
        if 'urgent' in headline_lower and claimed_source == 'UNKNOWN':
            reasons.append("Urgent claim from unknown source")
            score += 0.6
            
        return SuspicionResult(min(score, 1.0), reasons)
