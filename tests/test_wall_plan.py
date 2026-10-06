import json

from courier_runtime import surfaces as S


def test_16gb_mac_refuses_64_and_offers_8():
    plan = S.wall_plan(64, ram_gb=16)
    assert plan.verdict == "REFUSE"
    assert plan.limit == 12 and plan.recommended == 8
    assert "Lieber 8 Fenster" in plan.question()


def test_16gb_mac_warns_between_recommended_and_limit():
    assert S.wall_plan(12, ram_gb=16).verdict == "WARN"
    assert S.wall_plan(8, ram_gb=16).verdict == "OK"


def test_long_uptime_plans_smaller():
    assert S.wall_plan(8, ram_gb=16, uptime_hours=24 * 5).recommended == 6


def test_full_swap_refuses_any_new_window():
    plan = S.wall_plan(2, ram_gb=16, swap_pressure=True)
    assert plan.verdict == "REFUSE" and plan.recommended == 0


def test_already_open_windows_count_against_the_limit():
    plan = S.wall_plan(8, ram_gb=16, already_open=6)
    assert plan.verdict == "REFUSE" and plan.limit == 6 and plan.recommended == 2


def test_cli_exit_codes(monkeypatch, capsys):
    monkeypatch.setattr(S, "measure_host", lambda: (16 * 1.0, 2.0, False))
    assert S.main(["wall-check", "64"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["recommended"] == 8 and out["question"]
    assert S.main(["wall-check", "4"]) == 0
