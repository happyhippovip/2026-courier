"""Tests for Courier Symphony Arbitrage CLI."""

import json
from unittest.mock import patch
from courier_core.arbi.cli import main
from courier_core.arbi.models import NormalizedPair, OrderbookLevel, OrderbookSnapshot


def _mock_snapshot(exchange: str, pair: NormalizedPair, bid: float, ask: float) -> OrderbookSnapshot:
    return OrderbookSnapshot(
        exchange=exchange,
        pair=pair,
        bids=[OrderbookLevel(bid, 2.0)],
        asks=[OrderbookLevel(ask, 2.0)],
        timestamp_utc="2026-10-18T12:00:00Z",
    )


def test_cli_text_output(capsys):
    pair = NormalizedPair("BTC", "EUR")
    mock_provider = {
        "BTC/EUR": {
            "binance": _mock_snapshot("binance", pair, 60000.0, 60050.0),
            "kraken": _mock_snapshot("kraken", pair, 60300.0, 60350.0),
        }
    }

    with patch.object(
        NormalizedPair, "canonical", "BTC/EUR"
    ):
        code = main(["--dry-run", "--capital", "250"])
        assert code == 0
        captured = capsys.readouterr()
        assert "👑 COURIER AI ARBITRAGE · BINANCE ↔ KRAKEN" in captured.out
        assert "Simulated Net Profit:" in captured.out
        assert "Verified Actual Revenue: 0.0 EUR" in captured.out


def test_cli_json_output(capsys):
    code = main(["--dry-run", "--json", "--capital", "100"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["title"] == "👑 COURIER AI ARBITRAGE · BINANCE ↔ KRAKEN"
    assert data["simulation"]["status"] == "SIMULATED (NO REAL TRADES)"
    assert data["verified_actual_revenue"]["amount_eur"] == 0.0


def test_cli_dry_run_leaves_tracked_registry_untouched(capsys):
    # CI hygiene gate: test runs must not rewrite the tracked registry file.
    from pathlib import Path
    repo = Path(__file__).resolve().parents[2]
    registry = repo / "registries" / "arbitrage_research.json"
    before = registry.read_bytes()
    code = main(["--dry-run", "--capital", "100"])
    assert code == 0
    capsys.readouterr()
    assert registry.read_bytes() == before
