import json

from courier_runtime import surfaces as S


def test_16gb_mac_refuses_64_and_caps_at_8():
    plan = S.wall_plan(64, ram_gb=16)
    assert plan.verdict == "REFUSE"
    assert plan.limit == 8 and plan.recommended == 5
    assert "Lieber 5 Fenster" in plan.question()


def test_16gb_mac_warns_between_recommended_and_limit():
    assert S.wall_plan(8, ram_gb=16).verdict == "WARN"
    assert S.wall_plan(5, ram_gb=16).verdict == "OK"


def test_long_uptime_plans_smaller():
    assert S.wall_plan(3, ram_gb=16, uptime_hours=24 * 5).recommended == 3


def test_ramp_starts_at_three_windows():
    state = S.ramp_step({}, now=1000.0, open_count=0, pressure=False)
    plan = S.wall_plan(6, ram_gb=16, ramp=state["level"])
    assert state["level"] == 3 and plan.recommended == 3 and plan.verdict == "WARN"


def test_proven_ramp_allows_up_to_the_ram_limit():
    assert S.wall_plan(8, ram_gb=16, ramp=8).verdict == "OK"
    assert S.wall_plan(9, ram_gb=16, ramp=12).verdict == "REFUSE"


def test_ramp_climbs_one_window_after_calm_hours():
    h = 3600.0
    s = {"level": 3, "since": 0.0}
    assert S.ramp_step(s, now=1 * h, open_count=3, pressure=False)["level"] == 3   # not long enough
    assert S.ramp_step(s, now=2 * h, open_count=2, pressure=False)["level"] == 3   # level not used fully
    s = S.ramp_step(s, now=2 * h, open_count=3, pressure=False)
    assert s["level"] == 4
    s = S.ramp_step(s, now=4 * h, open_count=4, pressure=False)
    assert s["level"] == 5


def test_ramp_drops_to_start_after_panic_or_pressure():
    h = 3600.0
    s = {"level": 6, "since": 0.0}
    assert S.ramp_step(s, now=3 * h, open_count=6, pressure=False, last_panic=1 * h)["level"] == 3
    assert S.ramp_step(s, now=3 * h, open_count=6, pressure=True)["level"] == 3


def test_full_swap_refuses_any_new_window():
    plan = S.wall_plan(2, ram_gb=16, swap_pressure=True)
    assert plan.verdict == "REFUSE" and plan.recommended == 0


def test_already_open_windows_count_against_the_limit():
    plan = S.wall_plan(4, ram_gb=16, already_open=5)
    assert plan.verdict == "REFUSE" and plan.limit == 3 and plan.recommended == 0


def test_cli_exit_codes_and_ramp_state(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(S, "measure_host", lambda: (16 * 1.0, 2.0, False))
    monkeypatch.setattr(S, "last_panic_time", lambda: 0.0)
    state = tmp_path / "ramp.json"
    assert S.main(["wall-check", "64", "--state", str(state)]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["recommended"] == 3 and out["question"]
    assert json.loads(state.read_text())["level"] == 3
    assert S.main(["wall-check", "3", "--state", str(state)]) == 0


def test_last_panic_time_reads_newest_panic_report(tmp_path):
    (tmp_path / "Kernel-2026-10-06.panic").write_text("panic")
    (tmp_path / "other.ips").write_text("x")
    assert S.last_panic_time((str(tmp_path), str(tmp_path / "missing"))) > 0
    assert S.last_panic_time((str(tmp_path / "missing"),)) == 0.0
