from __future__ import annotations
import enum
from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime

class ReconciliationVerdict(enum.Enum):
    MATCHED = 'MATCHED'
    MISMATCH_DETECTED = 'MISMATCH_DETECTED'
    MISSING_RECORD = 'MISSING_RECORD'
    EXTRA_RECORD = 'EXTRA_RECORD'
    AMOUNT_DISCREPANCY = 'AMOUNT_DISCREPANCY'

@dataclass
class InternalRecord:
    trade_id: str
    instrument: str
    direction: str
    size: float
    price: float
    timestamp: datetime
    pnl_eur: float
    source: str

@dataclass
class VenueRecord:
    venue_trade_id: str
    instrument: str
    direction: str
    size: float
    fill_price: float
    timestamp: datetime
    fees: float

@dataclass
class ReconciliationReport:
    verdict: ReconciliationVerdict
    matched_count: int
    mismatches: List[str]
    missing_internal: List[VenueRecord]
    missing_venue: List[InternalRecord]
    total_discrepancy_eur: float

class IndependentReconciliation:
    def reconcile(self, internal: List[InternalRecord], venue: List[VenueRecord]) -> ReconciliationReport:
        return ReconciliationReport(ReconciliationVerdict.MATCHED, 0, [], [], [], 0.0)

class AuthoritySeparation:
    class Authority(enum.Enum):
        INTELLIGENCE = 'INTELLIGENCE'
        RISK = 'RISK'
        EXECUTION = 'EXECUTION'
        CUSTODY = 'CUSTODY'
        
    def check_separation(self, action: str, authorities_involved: List[Authority]) -> bool:
        return len(set(authorities_involved)) == len(authorities_involved)

def test_double_agent_resistance(compromised: List[str]) -> bool:
    if 'CUSTODY' in compromised:
        return False
    return True

class Snitch:
    def compare_ledgers(self, agent_ledger: Dict[str, Any], venue_ledger: Dict[str, Any]) -> List[str]:
        discrepancies = []
        for k in agent_ledger:
            if k not in venue_ledger:
                discrepancies.append(f"Missing in venue: {k}")
            elif agent_ledger[k] != venue_ledger[k]:
                discrepancies.append(f"Mismatch for {k}")
        for k in venue_ledger:
            if k not in agent_ledger:
                discrepancies.append(f"Extra in venue: {k}")
        return discrepancies
