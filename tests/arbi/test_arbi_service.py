"""Integration tests for Arbitrage Research Service and Pipeline Runner."""

import json
from pathlib import Path
from courier_core.arbi.models import NormalizedPair, OrderbookLevel, OrderbookSnapshot
from courier_core.arbi.service import ArbitrageResearchPipeline


def _mock_snapshot(exchange: str, pair: NormalizedPair, bid: float, ask: float) -> OrderbookSnapshot:
    return OrderbookSnapshot(
        exchange=exchange,
        pair=pair,
        bids=[OrderbookLevel(bid, 2.0)],
        asks=[OrderbookLevel(ask, 2.0)],
        timestamp_utc="2026-10-18T12:00:00Z",
    )


def test_arbitrage_pipeline_cycle_execution(tmp_path: Path):
    pipeline = ArbitrageResearchPipeline(root=tmp_path, virtual_capital_usd=100.0)

    # Provide offline deterministic mock data for Binance & Kraken
    pair = NormalizedPair("BTC", "EUR")
    mock_provider = {
        "BTC/EUR": {
            "binance": _mock_snapshot("binance", pair, 60000.0, 60050.0),
            "kraken": _mock_snapshot("kraken", pair, 60300.0, 60350.0),
        }
    }

    result = pipeline.run_cycle(pairs=[pair], books_provider=mock_provider)

    assert result["title"] == "👑 COURIER AI ARBITRAGE · BINANCE ↔ KRAKEN"
    assert result["simulation"]["status"] == "SIMULATED (NO REAL TRADES)"
    assert result["simulation"]["best_simulated_strategy"] == "Cross-Exchange Spot (Binance ↔ Kraken)"
    assert result["verified_actual_revenue"]["amount_eur"] == 0.00
    assert len(result["pairs_monitored"]) == 1
    assert result["pairs_monitored"][0]["pair"] == "BTC/EUR"
    assert result["pairs_monitored"][0]["venues"] == ["Binance", "Kraken"]

    # Verify output written to registry file
    registry_file = tmp_path / "registries" / "arbitrage_research.json"
    assert registry_file.is_file()
    saved = json.loads(registry_file.read_text(encoding="utf-8"))
    assert saved["title"] == result["title"]
    assert saved["simulation"]["best_simulated_strategy"] == "Cross-Exchange Spot (Binance ↔ Kraken)"
    assert saved["simulation"]["status"] == "SIMULATED (NO REAL TRADES)"
