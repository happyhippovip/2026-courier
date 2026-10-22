"""L2 WebSocket Stream Provider Protocol & Deterministic Mock Feeder for Binance and Kraken.

Safety Invariants:
- Zero real trading, zero wallet interaction (REAL_TRADES=0, WALLET_SIGNING=NO).
- Zero paid API calls / unauthenticated public streaming endpoints only.
- Deterministic offline replay stream for reproducible testing without network dependencies.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Callable, Iterator, Optional

from courier_core.arbi.models import (
    NormalizedPair,
    OrderbookLevel,
    OrderbookSnapshot,
    SymbolMapper,
    utc_iso_now,
)


@dataclass
class L2DeltaEvent:
    exchange: str
    pair: NormalizedPair
    bids_updated: list[OrderbookLevel]
    asks_updated: list[OrderbookLevel]
    timestamp_utc: str
    sequence_id: int


class L2StreamMockFeeder:
    """Simulates an incoming stream of L2 orderbook deltas for latency and race-condition audits."""

    def __init__(self, pair: NormalizedPair, initial_mid: float = 60000.0):
        if isinstance(initial_mid, bool):
            raise ValueError("Bool is not a number.")
        if not isinstance(initial_mid, (int, float)) or not math.isfinite(initial_mid):
            raise ValueError("mid is not a number.")
        if initial_mid <= 0:
            raise ValueError("mid is out of range.")
        self.pair = pair
        self.mid = initial_mid
        self._seq = 0

    def generate_events(self, count: int = 10) -> Iterator[L2DeltaEvent]:
        if isinstance(count, bool):
            raise ValueError("Bool is not a number.")
        if not isinstance(count, int):
            raise ValueError("count is not a number.")
        if count < 0:
            raise ValueError("count is out of range.")
        for i in range(count):
            self._seq += 1
            # Micro-shift in spread: alternating between Binance and Kraken
            ex = "binance" if i % 2 == 0 else "kraken"
            shift = (i * 1.5) if i % 4 == 0 else -(i * 0.8)
            bid_p = self.mid + shift
            ask_p = bid_p + 1.2

            yield L2DeltaEvent(
                exchange=ex,
                pair=self.pair,
                bids_updated=[OrderbookLevel(price=round(bid_p, 2), amount=1.5)],
                asks_updated=[OrderbookLevel(price=round(ask_p, 2), amount=1.5)],
                timestamp_utc=utc_iso_now(),
                sequence_id=self._seq,
            )


class L2OrderbookBookkeeper:
    """Maintains in-memory orderbook state updated by incoming L2 deltas."""

    def __init__(self, exchange: str, pair: NormalizedPair):
        self.exchange = exchange
        self.pair = pair
        self.bids: dict[float, float] = {}  # price -> amount
        self.asks: dict[float, float] = {}  # price -> amount
        self.last_sequence: int = 0
        self.last_update_utc: str = utc_iso_now()

    def apply_delta(self, event: L2DeltaEvent) -> None:
        if event.exchange != self.exchange or event.pair != self.pair:
            return

        sequence = event.sequence_id
        if isinstance(sequence, bool):
            raise ValueError("Bool is not a number.")
        if not isinstance(sequence, int):
            raise ValueError("sequence is not a number.")
        if sequence < 0:
            raise ValueError("sequence is out of range.")

        self._apply_levels(self.bids, event.bids_updated)
        self._apply_levels(self.asks, event.asks_updated)

        self.last_sequence = event.sequence_id
        self.last_update_utc = event.timestamp_utc

    def _apply_levels(self, book: dict, levels: list[OrderbookLevel]) -> None:
        for level in levels:
            if isinstance(level.price, bool) or isinstance(level.amount, bool):
                raise ValueError("Bool is not a number.")
            if not isinstance(level.price, (int, float)) or not math.isfinite(level.price):
                raise ValueError("price is not a number.")
            if level.price <= 0:
                raise ValueError("price is out of range.")
            if not isinstance(level.amount, (int, float)) or not math.isfinite(level.amount):
                raise ValueError("amount is not a number.")
            if level.amount < 0:
                raise ValueError("amount is out of range.")
            if level.amount <= 0:
                book.pop(level.price, None)
            else:
                book[level.price] = level.amount

    def to_snapshot(self) -> OrderbookSnapshot:
        # Sort bids descending, asks ascending
        sorted_bids = [
            OrderbookLevel(p, q) for p, q in sorted(self.bids.items(), key=lambda x: x[0], reverse=True)
        ]
        sorted_asks = [
            OrderbookLevel(p, q) for p, q in sorted(self.asks.items(), key=lambda x: x[0])
        ]
        return OrderbookSnapshot(
            exchange=self.exchange,
            pair=self.pair,
            bids=sorted_bids,
            asks=sorted_asks,
            timestamp_utc=self.last_update_utc,
            latency_ms=1.5,
        )
