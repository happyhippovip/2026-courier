"""The Windows daemon reads the controller token. The key is not config.json.

install.ps1 and bootstrap.ps1 write run/controller.token. A legacy config
key still works when no token file is present. The environment wins over both.
"""
from tests.test_windows_worker_contract import load_daemon

BOOTSTRAP = __import__("pathlib").Path(__file__).resolve().parents[1] / "scripts" / "windows_worker" / "bootstrap.ps1"


def test_bootstrap_does_not_store_the_api_key_in_config():
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert "COURIER_API_KEY = $apiKey" not in text
    assert "controller.token" in text
    assert "icacls $tokenPath /inheritance:r" in text
    assert "IsInputRedirected" in text
    assert "Pass -ServerArg." in text
    assert "Pass -ApiKeyArg." in text
    assert "LOCALAPPDATA" in text


def test_token_file_supplies_the_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "")
    daemon = load_daemon(tmp_path, monkeypatch)
    token = daemon.APP_DATA_DIR / "run" / "controller.token"
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text("token-from-file", encoding="utf-8")
    daemon.API_KEY = ""
    daemon.apply_config_credentials({"COURIER_API_KEY": "legacy-config-key", "COURIER_SERVER": "http://courier.invalid"})
    assert daemon.API_KEY == "token-from-file"


def test_legacy_config_key_is_used_when_no_token_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "")
    daemon = load_daemon(tmp_path, monkeypatch)
    daemon.API_KEY = ""
    daemon.apply_config_credentials({"COURIER_API_KEY": "legacy-config-key"})
    assert daemon.API_KEY == "legacy-config-key"


def test_environment_key_wins_over_the_token(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "from-env")
    daemon = load_daemon(tmp_path, monkeypatch)
    token = daemon.APP_DATA_DIR / "run" / "controller.token"
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text("token-from-file", encoding="utf-8")
    daemon.API_KEY = "from-env"
    daemon.apply_config_credentials({"COURIER_API_KEY": "legacy-config-key"})
    assert daemon.API_KEY == "from-env"


def test_token_symlink_is_not_adopted(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "")
    daemon = load_daemon(tmp_path, monkeypatch)
    outside = tmp_path / "foreign-token.txt"
    outside.write_text("foreign-token\n", encoding="utf-8")
    token = daemon.APP_DATA_DIR / "run" / "controller.token"
    token.parent.mkdir(parents=True, exist_ok=True)
    token.symlink_to(outside)
    assert daemon.read_controller_token() == ""
    assert outside.read_text(encoding="utf-8") == "foreign-token\n"


def test_token_under_symlinked_run_dir_is_not_adopted(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "")
    daemon = load_daemon(tmp_path, monkeypatch)
    target = tmp_path / "target"
    target.mkdir()
    (target / "controller.token").write_text("foreign-token\n", encoding="utf-8")
    run = daemon.APP_DATA_DIR / "run"
    run.symlink_to(target, target_is_directory=True)
    assert daemon.read_controller_token() == ""
    assert (target / "controller.token").read_text(encoding="utf-8") == "foreign-token\n"


def test_config_symlink_is_not_adopted(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    outside = tmp_path / "foreign-config.json"
    outside.write_text(
        '{"COURIER_API_KEY": "foreign-key", "COURIER_SERVER": "http://evil.invalid"}\n',
        encoding="utf-8",
    )
    config = daemon.APP_DATA_DIR / "config.json"
    config.unlink()
    config.symlink_to(outside)
    loaded = None
    try:
        loaded = daemon.load_config()
    except OSError as exc:
        assert "symlink" in str(exc)
    assert loaded is None
    assert outside.read_text(encoding="utf-8").startswith('{"COURIER_API_KEY": "foreign-key"')


def test_missing_key_still_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "")
    daemon = load_daemon(tmp_path, monkeypatch)
    daemon.API_KEY = ""
    daemon.apply_config_credentials({"COURIER_API_KEY": ""})
    try:
        daemon.require_api_key()
    except daemon.MissingCredentialError as exc:
        assert "COURIER_API_KEY is not set" in str(exc)
    else:
        raise AssertionError("missing key was accepted")
