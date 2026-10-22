"""Integration tests for Arbitrage Research Service and Pipeline Runner."""

import json
from pathlib import Path
from courier_core.arbi.models import NormalizedPair, OrderbookLevel, OrderbookSnapshot
from courier_core.arbi.scanner import MultiExchangeScanner
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


def test_empty_cycle_does_not_invent_simulation_numbers(tmp_path: Path, monkeypatch):
    calls = []

    def scan(cls, pair):
        calls.append(pair.canonical)
        return {"binance": None, "kraken": None}

    monkeypatch.setattr(MultiExchangeScanner, "scan_pair_all_venues", classmethod(scan))
    pipeline = ArbitrageResearchPipeline(root=tmp_path, persist=False)
    empty = pipeline.run_cycle(pairs=[])

    pair = NormalizedPair("BTC", "EUR")
    flat = {
        "BTC/EUR": {
            "binance": _mock_snapshot("binance", pair, 100.0, 100.0),
            "kraken": _mock_snapshot("kraken", pair, 100.0, 100.0),
        }
    }
    measured = pipeline.run_cycle(pairs=[pair], books_provider=flat)
    standby = pipeline.run_cycle(
        pairs=[pair],
        books_provider={"BTC/EUR": {"binance": None, "kraken": None}},
    )
    empty_sim = empty["simulation"]
    measured_sim = measured["simulation"]
    assert (
        calls == []
        and empty["pairs_monitored"] == []
        and empty_sim["net_simulated_profit_eur"] == 0.0
        and empty_sim["simulated_loss_eur"] == 0.0
        and empty_sim["net_roi_pct"] == 0.0
        and empty_sim["gross_opportunity_eur"] == 0.0
        and empty_sim["estimated_fees_eur"] == 0.0
        and empty_sim["estimated_slippage_eur"] == 0.0
        and empty_sim["opportunities_detected"] == 0
        and empty_sim["opportunities_executable"] == 0
        and empty_sim["simulation_runs"] == 0
        and empty_sim["success_rate_pct"] == 0.0
        and empty["verified_actual_revenue"]["amount_eur"] == 0.0
        and measured_sim["net_simulated_profit_eur"] == 0.0
        and measured_sim["simulated_loss_eur"] == 0.0
        and measured_sim["opportunities_executable"] == 0
        and measured_sim["simulation_runs"] == 0
        and measured_sim["success_rate_pct"] == 0.0
        and measured_sim["opportunities_detected"] == 2
        and standby["pairs_monitored"] == [
            {"pair": "BTC/EUR", "venues": [], "spread_bps": 0.0, "status": "standby"}
        ]
    ), {
        "calls": calls,
        "empty": empty_sim,
        "empty_pairs": empty["pairs_monitored"],
        "measured": measured_sim,
        "standby": standby["pairs_monitored"],
    }
