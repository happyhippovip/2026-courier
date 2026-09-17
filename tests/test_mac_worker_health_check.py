import subprocess
import shutil

from scripts.mac_worker import health_check


def test_health_check_requires_both_keychain_items(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(health_check, "STATE_DIR", tmp_path)

    def fake_check_output(command, **kwargs):
        if command[:2] == ["launchctl", "list"]:
            return b"com.courier.mac_worker"
        service = command[command.index("-s") + 1]
        if service == "courier_server_url":
            return b"metadata only"
        raise subprocess.CalledProcessError(44, command)

    monkeypatch.setattr(health_check.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(shutil, "which", lambda *args, **kwargs: None)

    health_check.run()

    output = capsys.readouterr().out
    assert "launchd worker status: RUNNING" in output
    assert "Keychain credentials: FOUND" not in output
    assert "courier_api_key missing or inaccessible" in output
