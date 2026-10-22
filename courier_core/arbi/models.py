"""Courier Symphony — Arbitrage Models & Symbol Normalization.

Pure data classes and normalization rules for Binance, Bybit, and OKX Spot markets.
Absolute invariants:
- REAL_TRADES=0, REAL_FUNDS_TOUCHED=NO, WALLET_SIGNING=NO.
- Zero API cost / public endpoints only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class NormalizedPair:
    base: str   # e.g. "BTC"
    quote: str  # e.g. "USDT", "EUR"

    @property
    def canonical(self) -> str:
        return f"{self.base}/{self.quote}"

    @classmethod
    def parse_canonical(cls, canonical: str) -> NormalizedPair:
        parts = canonical.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid canonical pair: {canonical}")
        return cls(base=parts[0].upper(), quote=parts[1].upper())


class SymbolMapper:
    """Translates between canonical pairs (BTC/USDT) and exchange symbols."""

    @staticmethod
    def to_exchange_symbol(exchange: str, pair: NormalizedPair) -> str:
        ex = exchange.lower()
        if ex == "binance":
            return f"{pair.base}{pair.quote}"  # e.g. BTCUSDT, BTCEUR
        elif ex == "kraken":
            # Kraken standard mapping: BTC is XBT on Kraken
            base = "XBT" if pair.base.upper() == "BTC" else pair.base.upper()
            quote = pair.quote.upper()
            return f"{base}{quote}"  # e.g. XBTEUR, XBTUSDT, ETHEUR
        elif ex == "bybit":
            return f"{pair.base}{pair.quote}"  # e.g. BTCUSDT
        elif ex == "okx":
            return f"{pair.base}-{pair.quote}"  # e.g. BTC-USDT
        else:
            raise ValueError(f"Unsupported exchange for mapping: {exchange}")

    @staticmethod
    def from_exchange_symbol(exchange: str, symbol: str) -> NormalizedPair:
        ex = exchange.lower()
        sym = symbol.upper()
        if ex == "kraken":
            # Normalize legacy Kraken prefixes like XXBT, XETH, ZEUR, ZUSD
            if sym.startswith("XXBT") or sym.startswith("XETH"):
                base = sym[1:4]
                quote = sym[4:]
                if quote.startswith("Z"): quote = quote[1:]
                base_norm = "BTC" if base == "XBT" else base
                return NormalizedPair(base_norm, quote)
            for quote in ("EUR", "USD", "USDT", "USDC", "GBP", "CHF"):
                if sym.endswith(quote):
                    base = sym[:-len(quote)]
                    base_norm = "BTC" if base in ("XBT", "XXBT") else base
                    return NormalizedPair(base_norm, quote)
            raise ValueError(f"Cannot parse Kraken symbol: {symbol}")
        if ex == "okx":
            parts = sym.split("-")
            if len(parts) >= 2:
                return NormalizedPair(parts[0], parts[1])
            raise ValueError(f"Cannot parse OKX symbol: {symbol}")
        # For Binance / Bybit without separator, common quote currencies
        for quote in ("USDT", "USDC", "EUR", "USD", "BTC", "ETH"):
            if sym.endswith(quote) and len(sym) > len(quote):
                base = sym[:-len(quote)]
                return NormalizedPair(base, quote)
        raise ValueError(f"Cannot parse {exchange} symbol: {symbol}")


@dataclass
class OrderbookLevel:
    price: float
    amount: float


@dataclass
class OrderbookSnapshot:
    exchange: str
    pair: NormalizedPair
    bids: list[OrderbookLevel]  # sorted highest price first
    asks: list[OrderbookLevel]  # sorted lowest price first
    timestamp_utc: str
    latency_ms: float = 0.0
    is_stale: bool = False

    @property
    def best_bid(self) -> Optional[float]:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        return self.asks[0].price if self.asks else None

    @property
    def spread_bps(self) -> Optional[float]:
        bid = self.best_bid
        ask = self.best_ask
        if (
            isinstance(bid, (int, float))
            and isinstance(ask, (int, float))
            and math.isfinite(bid)
            and math.isfinite(ask)
            and bid
            and ask
            and ask > 0
        ):
            return ((ask - bid) / ask) * 10000.0
        return None


@dataclass
class ExchangeFeeSchedule:
    exchange: str
    maker_fee_pct: float
    taker_fee_pct: float
    withdrawal_fee_usd: float = 0.0
    tier: str = "VIP0 / Retail"


DEFAULT_FEE_SCHEDULES: dict[str, ExchangeFeeSchedule] = {
    "binance": ExchangeFeeSchedule(exchange="binance", maker_fee_pct=0.10, taker_fee_pct=0.10, withdrawal_fee_usd=1.0),
    "kraken": ExchangeFeeSchedule(exchange="kraken", maker_fee_pct=0.16, taker_fee_pct=0.26, withdrawal_fee_usd=1.5),
    "bybit": ExchangeFeeSchedule(exchange="bybit", maker_fee_pct=0.10, taker_fee_pct=0.10, withdrawal_fee_usd=1.0),
    "okx": ExchangeFeeSchedule(exchange="okx", maker_fee_pct=0.08, taker_fee_pct=0.10, withdrawal_fee_usd=1.0),
}
