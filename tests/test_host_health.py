from scripts.host_health import diagnose, main, render, snapshot


def snap(**kw):
    base = {"platform": "win32", "taken_at": 0, "uptime_min": 600, "ram_total_gb": 16.0, "ram_used_pct": 50,
            "swap_used_pct": 10, "cpu_pct": 10, "disk_free_pct": 40, "process_count": 200, "groups": [],
            "startup": []}
    base.update(kw)
    return base


def test_healthy_machine_says_ok():
    assert diagnose(snap()) == [("ok", diagnose(snap())[0][1])]


def test_full_ram_and_the_ai_tool_behind_it():
    f = diagnose(snap(ram_used_pct=92, groups=[{"name": "antigravity", "count": 17, "rss_gb": 11.7}]))
    assert f[0][0] == "high" and "fast voll" in f[0][1]
    assert any("antigravity: 11.7 GB in 17 Prozessen" in m and "1–2" in m for _, m in f)


def test_right_after_restart_updates_are_explained_not_alarmed():
    f = diagnose(snap(uptime_min=8, groups=[{"name": "tiworker", "count": 1, "rss_gb": 0.8},
                                            {"name": "msmpeng", "count": 1, "rss_gb": 0.4}],
                      startup=[{"name": f"app{i}", "where": "HKCU Run", "command": "x"} for i in range(12)]))
    msgs = " ".join(m for _, m in f)
    assert "erst seit 8 Minuten" in msgs and "nicht abbrechen" in msgs and "12 Programme starten automatisch" in msgs


def test_swap_and_disk():
    f = diagnose(snap(ram_used_pct=85, swap_used_pct=70, disk_free_pct=5))
    assert sum(1 for sev, _ in f if sev == "high") == 2


def test_live_snapshot_runs_read_only(capsys):
    s = snapshot()
    assert s["ram_total_gb"] > 0 and isinstance(s["groups"], list)
    assert "Dieser Check liest nur" in render(s, diagnose(s))
    assert main([]) == 0 and "BEFUND" in capsys.readouterr().out
