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


def test_registry_does_not_follow_a_symlink(tmp_path: Path):
    pair = NormalizedPair("BTC", "EUR")
    books = {
        "BTC/EUR": {
            "binance": _mock_snapshot("binance", pair, 100.0, 100.0),
            "kraken": _mock_snapshot("kraken", pair, 100.0, 100.0),
        }
    }
    outside = tmp_path / "outside.json"
    outside.write_text("keep", encoding="utf-8")
    root = tmp_path / "root"
    registry_dir = root / "registries"
    registry_dir.mkdir(parents=True)
    (registry_dir / "arbitrage_research.json").symlink_to(outside)

    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (outside_dir / "keep.txt").write_text("keep", encoding="utf-8")
    linked_root = tmp_path / "linked-root"
    linked_root.mkdir()
    (linked_root / "registries").symlink_to(outside_dir)

    errors = []
    for cycle_root in (root, linked_root):
        pipeline = ArbitrageResearchPipeline(root=cycle_root, persist=True)
        try:
            pipeline.run_cycle(pairs=[pair], books_provider=books)
        except ValueError as exc:
            errors.append(str(exc))
    written = outside.read_text(encoding="utf-8")
    leaked = sorted(p.name for p in outside_dir.iterdir())
    assert errors == ["refusing to follow a symlink", "refusing to follow a symlink"] and written == "keep" and leaked == ["keep.txt"], {
        "errors": errors,
        "outside": written[:80],
        "leaked": leaked,
    }


def test_bool_depth_limit_is_not_requested(monkeypatch):
    urls = []

    def capture(url):
        urls.append(url)
        raise AssertionError(url)

    monkeypatch.setattr(MultiExchangeScanner, "_fetch_json", capture)
    pair = NormalizedPair("BTC", "EUR")
    venues = (
        ("binance", MultiExchangeScanner.fetch_binance_depth),
        ("bybit", MultiExchangeScanner.fetch_bybit_depth),
        ("okx", MultiExchangeScanner.fetch_okx_depth),
        ("kraken", MultiExchangeScanner.fetch_kraken_depth),
    )
    seen = []
    for flag in (True, False):
        for name, fetch in venues:
            urls.clear()
            try:
                fetch(pair, flag)
            except ValueError as exc:
                seen.append((name, flag, "raised", str(exc), list(urls)))
            except AssertionError as exc:
                seen.append((name, flag, "fetched", str(exc)))
            else:
                seen.append((name, flag, "accepted", list(urls)))
    assert seen == [
        (name, flag, "raised", "Bool is not a number.", [])
        for flag in (True, False)
        for name, _fetch in venues
    ], seen
    urls.clear()
    try:
        MultiExchangeScanner.fetch_binance_depth(pair, 10)
    except AssertionError as exc:
        numeric = str(exc)
    else:
        numeric = ""
    assert numeric.endswith("limit=10"), numeric


def test_bool_book_level_is_not_a_price(monkeypatch):
    def payload(_url):
        return {"bids": [[True, "2.0"]], "asks": [["100.0", False]]}

    monkeypatch.setattr(MultiExchangeScanner, "_fetch_json", payload)
    pair = NormalizedPair("BTC", "EUR")
    try:
        snap = MultiExchangeScanner.fetch_binance_depth(pair, 10)
    except ValueError as exc:
        assert "bool" in str(exc).lower(), exc
    else:
        level = snap.bids[0]
        ask = snap.asks[0]
        raise AssertionError((level.price, level.amount, ask.price, ask.amount))

    def numeric(_url):
        return {"bids": [["60000.5", "1.25"]], "asks": [["60010", "2"]]}

    monkeypatch.setattr(MultiExchangeScanner, "_fetch_json", numeric)
    snap = MultiExchangeScanner.fetch_binance_depth(pair, 10)
    assert (snap.bids[0].price, snap.bids[0].amount, snap.asks[0].price, snap.asks[0].amount) == (
        60000.5, 1.25, 60010.0, 2.0,
    )
