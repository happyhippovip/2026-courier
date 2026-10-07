import json

import pytest

from scripts.check_local_safety import main, scan, scan_text


@pytest.mark.parametrize("line", [
    "Stop-Process -Name python -Force",
    "Get-Process powershell | Where-Object { $_.Id -ne $PID } | Stop-Process -Force",
    "taskkill /F /IM Courier.exe 2>NUL",
    "pkill -9 -f gunicorn 2>/dev/null || true",
    "killall python",
    'subprocess.run(["taskkill", "/F", "/IM", "python.exe"])',
    'subprocess.run(["pkill", "-f", "courier"])',
    'if p.name() == "python.exe": p.kill()',
])
def test_name_based_kills_are_found(line):
    assert [rule for rule, _, _ in scan_text(line)] == ["KILL_BY_NAME"]


@pytest.mark.parametrize("line", [
    'app.run(host="0.0.0.0", port=8080)',
    'socketserver.TCPServer(("", port), handler)',
    "server.bind(('0.0.0.0', 9000))",
    "uvicorn app:app --host 0.0.0.0",
    "var listener = new TcpListener(IPAddress.Any, port);",
    'HOST = "0.0.0.0"',
    "sock.bind(('::', port))",
    "gunicorn -w 1 --threads 4 -b 0.0.0.0:8080 server.app:app &",
    "gunicorn --bind=0.0.0.0:8000 app:app",
])
def test_wildcard_binds_are_found(line):
    assert [rule for rule, _, _ in scan_text(line)] == ["WILDCARD_BIND"]


@pytest.mark.parametrize("line", [
    "Stop-Process -Id $proc.Id -Force",
    "taskkill /F /T /PID 4242",
    "os.killpg(pgid, signal.SIGTERM)",
    'app.run(host="127.0.0.1", port=port)',
    'socketserver.TCPServer(("127.0.0.1", port), handler)',
    "# never use pkill-style cleanup",
    "proc = psutil.Process(owned_pid); proc.kill()",
    'subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)])',
    "listen on loopback, not 0.0.0.0 or the LAN",
    'subprocess.run(["taskkill", "/IM", "x.exe"])  # local-safety: allow test fixture only',
    "# never: pkill -f gunicorn (kills foreign servers)",
    "REM taskkill /F /IM python.exe was removed",
    "gunicorn -b 127.0.0.1:8080 server.app:app",
])
def test_owned_kills_and_loopback_binds_are_clean(line):
    assert list(scan_text(line)) == []


def test_allow_pragma_needs_a_reason():
    assert [r for r, _, _ in scan_text('app.run(host="0.0.0.0")  # local-safety: allow')] == ["WILDCARD_BIND"]


def _tree(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "stop.bat").write_text("taskkill /F /IM Courier.exe\n")
    (tmp_path / "server.py").write_text('app.run(host="0.0.0.0", port=8080)\n')
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "rule.sh").write_text("pkill python\n")  # docs are not code
    return tmp_path


def test_scan_reports_paths_and_skips_docs(tmp_path):
    found = {(f["rule"], f["path"]) for f in scan(str(_tree(tmp_path)))}
    assert found == {("KILL_BY_NAME", "scripts/stop.bat"), ("WILDCARD_BIND", "server.py")}


def test_baseline_ratchet_blocks_only_new_findings(tmp_path, capsys):
    root = _tree(tmp_path)
    baseline = tmp_path / "baseline.json"
    assert main([str(root), "--write-baseline", str(baseline)]) == 0
    assert len(json.loads(baseline.read_text())) == 2
    assert main([str(root), "--baseline", str(baseline)]) == 0

    (root / "cleanup.ps1").write_text("Stop-Process -Name python -Force\n")
    assert main([str(root), "--baseline", str(baseline)]) == 1
    assert "NEW KILL_BY_NAME cleanup.ps1:1" in capsys.readouterr().out


def test_moving_a_known_line_is_not_new(tmp_path):
    root = _tree(tmp_path)
    baseline = tmp_path / "baseline.json"
    main([str(root), "--write-baseline", str(baseline)])
    (root / "server.py").write_text('\n\napp.run(host="0.0.0.0",  port=8080)\n')
    assert main([str(root), "--baseline", str(baseline)]) == 0


def test_without_baseline_any_finding_fails(tmp_path):
    assert main([str(_tree(tmp_path))]) == 1
    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "ok.py").write_text('app.run(host="127.0.0.1")\n')
    assert main([str(clean)]) == 0
