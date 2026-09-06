from __future__ import annotations
import enum
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta

class DisclosureClass(enum.Enum):
    POSITION_SIZE = "POSITION_SIZE"
    ENTRY_PRICE = "ENTRY_PRICE"
    STOP_LOSS = "STOP_LOSS"
    LIQUIDATION_PRICE = "LIQUIDATION_PRICE"
    TAKE_PROFIT = "TAKE_PROFIT"
    LEVERAGE = "LEVERAGE"
    WALLET_ADDRESS = "WALLET_ADDRESS"
    ACCOUNT_ID = "ACCOUNT_ID"
    STRATEGY_SIGNAL = "STRATEGY_SIGNAL"
    BUDGET_AMOUNT = "BUDGET_AMOUNT"

class PostingVerdict(enum.Enum):
    ALLOW = "ALLOW"
    BLOCK_POSITION_OPEN = "BLOCK_POSITION_OPEN"
    BLOCK_DELAY_REQUIRED = "BLOCK_DELAY_REQUIRED"
    BLOCK_SENSITIVE_DATA = "BLOCK_SENSITIVE_DATA"

@dataclass
class TradingState:
    open_positions: List[str]
    closed_positions: Dict[str, datetime]
    trading_account_ids: List[str]
    wallet_fragments: List[str]

@dataclass
class FilterResult:
    verdict: PostingVerdict
    blocked_reasons: List[str]
    detected_leaks: List[DisclosureClass]
    safe_content_suggestion: str

class OpsecPolicy:
    POST_POSITION_DELAY_SECONDS = 86400

    def scan_text_for_leaks(self, text: str) -> List[DisclosureClass]:
        leaks = []
        text_lower = text.lower()
        
        if any(word in text_lower for word in ["long", "short", "position", "size"]):
            leaks.append(DisclosureClass.POSITION_SIZE)
        if any(word in text_lower for word in ["entry", "entered at"]):
            leaks.append(DisclosureClass.ENTRY_PRICE)
        if any(word in text_lower for word in ["stop", "sl", "stop loss"]):
            leaks.append(DisclosureClass.STOP_LOSS)
        if any(word in text_lower for word in ["liq", "liquidation"]):
            leaks.append(DisclosureClass.LIQUIDATION_PRICE)
        if any(word in text_lower for word in ["tp", "take profit", "target"]):
            leaks.append(DisclosureClass.TAKE_PROFIT)
        if any(word in text_lower for word in ["leverage", "x"]):
            if re.search(r'\b\d{1,3}x\b', text_lower):
                leaks.append(DisclosureClass.LEVERAGE)
                
        if re.search(r'\b0x[a-fA-F0-9]{40}\b', text) or re.search(r'\bbc1[a-zA-HJ-NP-Z0-9]{25,39}\b', text):
            leaks.append(DisclosureClass.WALLET_ADDRESS)
            
        if re.search(r'\bacc(ount)?_?[0-9a-zA-Z]{5,}\b', text_lower):
            leaks.append(DisclosureClass.ACCOUNT_ID)
            
        if any(word in text_lower for word in ["signal", "algo says", "model output"]):
            leaks.append(DisclosureClass.STRATEGY_SIGNAL)
            
        if re.search(r'[\$€]\s*\d+([,\.]\d+)?\b|\b\d+([,\.]\d+)?\s*(usd|eur|bucks)\b', text_lower):
            leaks.append(DisclosureClass.BUDGET_AMOUNT)
            
        return list(set(leaks))

    def evaluate_posting(self, text: str, open_positions: List[str], position_closed_at: Optional[datetime]) -> PostingVerdict:
        leaks = self.scan_text_for_leaks(text)
        if leaks:
            return PostingVerdict.BLOCK_SENSITIVE_DATA
            
        if open_positions:
            return PostingVerdict.BLOCK_POSITION_OPEN
            
        if position_closed_at:
            delay = timedelta(seconds=self.POST_POSITION_DELAY_SECONDS)
            if datetime.now(timezone.utc) - position_closed_at < delay:
                return PostingVerdict.BLOCK_DELAY_REQUIRED
                
        return PostingVerdict.ALLOW

    def check_trading_public_id_separation(self, trading_ids: List[str], public_content: str) -> bool:
        for tid in trading_ids:
            if tid in public_content:
                return False
        return True

    def create_social_media_leak_report(self, text: str) -> Dict:
        leaks = self.scan_text_for_leaks(text)
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "content_length": len(text),
            "leaks_detected": [leak.name for leak in leaks],
            "is_safe": len(leaks) == 0
        }

class SocialMediaFilter:
    def __init__(self, policy: OpsecPolicy = None):
        self.policy = policy or OpsecPolicy()

    def filter_outbound(self, content: str, trading_state: TradingState) -> FilterResult:
        leaks = self.policy.scan_text_for_leaks(content)
        
        for tid in trading_state.trading_account_ids:
            if tid in content:
                leaks.append(DisclosureClass.ACCOUNT_ID)
                
        for frag in trading_state.wallet_fragments:
            if frag in content:
                leaks.append(DisclosureClass.WALLET_ADDRESS)
                
        leaks = list(set(leaks))
        
        if leaks:
            return FilterResult(
                verdict=PostingVerdict.BLOCK_SENSITIVE_DATA,
                blocked_reasons=[f"Detected leaks: {[l.name for l in leaks]}"],
                detected_leaks=leaks,
                safe_content_suggestion="[REDACTED]"
            )
            
        if trading_state.open_positions:
            return FilterResult(
                verdict=PostingVerdict.BLOCK_POSITION_OPEN,
                blocked_reasons=["Cannot post while positions are open"],
                detected_leaks=[],
                safe_content_suggestion=""
            )
            
        if trading_state.closed_positions:
            most_recent_close = max(trading_state.closed_positions.values())
            delay = timedelta(seconds=self.policy.POST_POSITION_DELAY_SECONDS)
            if datetime.now(timezone.utc) - most_recent_close < delay:
                return FilterResult(
                    verdict=PostingVerdict.BLOCK_DELAY_REQUIRED,
                    blocked_reasons=["Required delay after position closure has not elapsed"],
                    detected_leaks=[],
                    safe_content_suggestion=""
                )
                
        return FilterResult(
            verdict=PostingVerdict.ALLOW,
            blocked_reasons=[],
            detected_leaks=[],
            safe_content_suggestion=content
        )
