"""Multi-Exchange Public Market Data Scanner (Binance, Bybit, OKX).

Uses strictly public, unauthenticated REST/Orderbook endpoints.
Zero API cost, zero credentials required.
"""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request
from typing import Optional

from courier_core.arbi.models import (
    NormalizedPair,
    OrderbookLevel,
    OrderbookSnapshot,
    SymbolMapper,
    utc_iso_now,
)


class MultiExchangeScanner:
    """Fetches public orderbook depths from Binance, Bybit, and OKX."""

    TIMEOUT_SEC = 4.0
    MAX_DEPTH = 10

    @staticmethod
    def _depth_count(limit: int) -> int:
        if isinstance(limit, bool):
            raise ValueError("Bool is not a number.")
        return limit

    @staticmethod
    def _finite_level_number(value, label: str) -> float:
        if isinstance(value, bool):
            raise ValueError("Bool is not a number.")
        if isinstance(value, (int, float)):
            number = float(value)
        elif isinstance(value, str):
            try:
                number = float(value)
            except ValueError:
                raise ValueError(f"{label} is not a number.") from None
        else:
            raise ValueError(f"{label} is not a number.")
        if not math.isfinite(number):
            raise ValueError(f"{label} is not a number.")
        return number

    @staticmethod
    def _book_level(price, amount) -> OrderbookLevel:
        return OrderbookLevel(
            MultiExchangeScanner._finite_level_number(price, "price"),
            MultiExchangeScanner._finite_level_number(amount, "amount"),
        )

    @staticmethod
    def _fetch_json(url: str) -> dict:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "CourierSymphony-ArbiResearch/1.0",
                "Accept": "application/json",
            },
        )
        ssl_ctx = None
        try:
            import certifi
            import ssl
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:  # noqa: BLE001
            pass

        with urllib.request.urlopen(req, timeout=MultiExchangeScanner.TIMEOUT_SEC, context=ssl_ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @classmethod
    def fetch_binance_depth(cls, pair: NormalizedPair, limit: int = 10) -> OrderbookSnapshot:
        limit = cls._depth_count(limit)
        symbol = SymbolMapper.to_exchange_symbol("binance", pair)
        url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit={limit}"
        t0 = time.time()
        data = cls._fetch_json(url)
        lat = (time.time() - t0) * 1000.0

        bids = [cls._book_level(p, q) for p, q in data.get("bids", [])]
        asks = [cls._book_level(p, q) for p, q in data.get("asks", [])]
        return OrderbookSnapshot(
            exchange="binance",
            pair=pair,
            bids=bids,
            asks=asks,
            timestamp_utc=utc_iso_now(),
            latency_ms=round(lat, 2),
        )

    @classmethod
    def fetch_bybit_depth(cls, pair: NormalizedPair, limit: int = 10) -> OrderbookSnapshot:
        limit = cls._depth_count(limit)
        symbol = SymbolMapper.to_exchange_symbol("bybit", pair)
        url = f"https://api.bybit.com/v5/market/orderbook?category=spot&symbol={symbol}&limit={limit}"
        t0 = time.time()
        data = cls._fetch_json(url)
        lat = (time.time() - t0) * 1000.0

        result = data.get("result", {})
        raw_bids = result.get("b", [])
        raw_asks = result.get("a", [])
        bids = [cls._book_level(p, q) for p, q in raw_bids]
        asks = [cls._book_level(p, q) for p, q in raw_asks]
        return OrderbookSnapshot(
            exchange="bybit",
            pair=pair,
            bids=bids,
            asks=asks,
            timestamp_utc=utc_iso_now(),
            latency_ms=round(lat, 2),
        )

    @classmethod
    def fetch_okx_depth(cls, pair: NormalizedPair, limit: int = 10) -> OrderbookSnapshot:
        limit = cls._depth_count(limit)
        symbol = SymbolMapper.to_exchange_symbol("okx", pair)
        url = f"https://www.okx.com/api/v5/market/books?instId={symbol}&sz={limit}"
        t0 = time.time()
        data = cls._fetch_json(url)
        lat = (time.time() - t0) * 1000.0

        book_data = data.get("data", [{}])[0]
        raw_bids = book_data.get("bids", [])
        raw_asks = book_data.get("asks", [])
        bids = [cls._book_level(x[0], x[1]) for x in raw_bids]
        asks = [cls._book_level(x[0], x[1]) for x in raw_asks]
        return OrderbookSnapshot(
            exchange="okx",
            pair=pair,
            bids=bids,
            asks=asks,
            timestamp_utc=utc_iso_now(),
            latency_ms=round(lat, 2),
        )

    @classmethod
    def fetch_kraken_depth(cls, pair: NormalizedPair, count: int = 10) -> OrderbookSnapshot:
        count = cls._depth_count(count)
        symbol = SymbolMapper.to_exchange_symbol("kraken", pair)
        url = f"https://api.kraken.com/0/public/Depth?pair={symbol}&count={count}"
        t0 = time.time()
        data = cls._fetch_json(url)
        lat = (time.time() - t0) * 1000.0

        result = data.get("result", {})
        # Kraken keys the result by the internal pair name (e.g. XXBTZEUR or XBTEUR)
        book_key = next(iter(result.keys())) if result else None
        book = result.get(book_key, {}) if book_key else {}
        raw_bids = book.get("bids", [])
        raw_asks = book.get("asks", [])
        # Kraken depth format: [price, amount, timestamp]
        bids = [cls._book_level(x[0], x[1]) for x in raw_bids]
        asks = [cls._book_level(x[0], x[1]) for x in raw_asks]
        return OrderbookSnapshot(
            exchange="kraken",
            pair=pair,
            bids=bids,
            asks=asks,
            timestamp_utc=utc_iso_now(),
            latency_ms=round(lat, 2),
        )

    @classmethod
    def scan_pair_all_venues(cls, pair: NormalizedPair) -> dict[str, Optional[OrderbookSnapshot]]:
        """Strict V43 invariant: EXCHANGES_ALLOWED = [Binance Spot, Kraken Spot]."""
        results: dict[str, Optional[OrderbookSnapshot]] = {}
        for ex, fetcher in [
            ("binance", cls.fetch_binance_depth),
            ("kraken", cls.fetch_kraken_depth),
        ]:
            try:
                results[ex] = fetcher(pair)
            except Exception:  # noqa: BLE001
                # Fail-closed: record None if unavailable
                results[ex] = None
        return results

