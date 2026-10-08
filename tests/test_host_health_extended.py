import json
from scripts.host_health import diagnose, render, main


def test_diagnose_high_cpu():
    snap = {
        "platform": "darwin",
        "taken_at": 1000.0,
        "uptime_min": 120,
        "ram_total_gb": 32.0,
        "ram_used_pct": 50,
        "swap_used_pct": 0,
        "cpu_pct": 98,
        "disk_free_pct": 50,
        "process_count": 150,
        "groups": [{"name": "compile_runner", "count": 1, "rss_gb": 2.0}],
        "startup": [],
    }
    findings = diagnose(snap)
    assert any(sev == "medium" and f"Prozessor voll ausgelastet ({snap['cpu_pct']:.0f} %)." in msg for sev, msg in findings)


def test_render_contains_all_major_sections():
    snap = {
        "platform": "darwin",
        "taken_at": 1000.0,
        "uptime_min": 60,
        "ram_total_gb": 16.0,
        "ram_used_pct": 60,
        "swap_used_pct": 5,
        "cpu_pct": 15,
        "disk_free_pct": 30,
        "process_count": 80,
        "groups": [{"name": "python", "count": 2, "rss_gb": 1.2}],
        "startup": [{"name": "item1", "where": "/LaunchAgents", "command": "run.plist"}],
    }
    findings = diagnose(snap)
    rendered = render(snap, findings)

    assert "Computer-Check (darwin)" in rendered
    assert "RAM 60 % von 16.0 GB" in rendered
    assert "GRÖSSTE PROGRAMME:" in rendered
    assert "AUTOSTART:" in rendered
    assert "BEFUND:" in rendered


def test_main_with_json_export(tmp_path):
    report_file = tmp_path / "health_report.json"
    ret = main(["--json", str(report_file)])
    assert ret == 0
    assert report_file.exists()

    data = json.loads(report_file.read_text(encoding="utf-8"))
    assert "snapshot" in data
    assert "findings" in data
    assert "ram_total_gb" in data["snapshot"]
