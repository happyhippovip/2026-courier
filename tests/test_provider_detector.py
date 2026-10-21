"""Tests for fail-closed provider CLI surface and capability detector (S04)."""
from __future__ import annotations

import json
import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from courier_core.provider_detector import (
    ProviderCapabilityInfo,
    detect_all_providers,
    detect_provider_cli,
    main,
)


def test_invalid_provider_name_fails_closed():
    res = detect_provider_cli("")
    assert not res.available
    assert res.reason == "INVALID_PROVIDER_NAME"

    res_none = detect_provider_cli(None)  # type: ignore
    assert not res_none.available
    assert res_none.reason == "INVALID_PROVIDER_NAME"


def test_unallowlisted_provider_fails_closed():
    res = detect_provider_cli("openai_api")
    assert not res.available
    assert res.reason == "PROVIDER_NOT_ALLOWLISTED"

    res_anthropic = detect_provider_cli("claude")
    assert not res_anthropic.available
    assert res_anthropic.reason == "PROVIDER_NOT_ALLOWLISTED"


def test_missing_binary_fails_closed():
    res = detect_provider_cli("agy", config={"binaries": {"agy": "/non/existent/agy"}})
    assert not res.available
    assert res.reason == "BINARY_MISSING"


def test_mock_agy_cli_probe_success(tmp_path: Path):
    # Create fake agy script
    fake_agy = tmp_path / "fake_agy.py"
    fake_agy.write_text(
        "import sys\n"
        "if '--version' in sys.argv:\n"
        "    print('antigravity 1.3.1 (sandbox, json-output, print-timeout)')\n"
        "    sys.exit(0)\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    fake_agy.chmod(fake_agy.stat().st_mode | stat.S_IEXEC | stat.S_IREAD)

    config = {"binaries": {"agy": str(fake_agy.resolve())}}
    res = detect_provider_cli("agy", config=config)

    assert res.available
    assert res.version == "1.3.1"
    assert "headless" in res.capabilities
    assert "sandbox" in res.capabilities
    assert "json_output" in res.capabilities
    assert "print_timeout" in res.capabilities
    assert res.reason == "CLI_DETECTED"


def test_mock_muse_cli_probe_success(tmp_path: Path):
    fake_muse = tmp_path / "fake_muse.py"
    fake_muse.write_text(
        "import sys\n"
        "if '--version' in sys.argv:\n"
        "    print('muse 2.0.4 exec --prompt-file --reasoning-effort')\n"
        "    sys.exit(0)\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    fake_muse.chmod(fake_muse.stat().st_mode | stat.S_IEXEC | stat.S_IREAD)

    config = {"binaries": {"muse": str(fake_muse.resolve())}}
    res = detect_provider_cli("muse", config=config)

    assert res.available
    assert res.version == "2.0.4"
    assert "headless" in res.capabilities
    assert "exec_subcommand" in res.capabilities
    assert "prompt_file" in res.capabilities
    assert "reasoning_effort" in res.capabilities
    assert res.reason == "CLI_DETECTED"


def test_probe_timeout_fails_closed(tmp_path: Path):
    fake_hanging = tmp_path / "fake_hang.py"
    fake_hanging.write_text(
        "import time, sys\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    fake_hanging.chmod(fake_hanging.stat().st_mode | stat.S_IEXEC | stat.S_IREAD)

    config = {"binaries": {"agy": str(fake_hanging.resolve())}}
    res = detect_provider_cli("agy", config=config, timeout_s=0.5)

    assert not res.available
    assert res.reason == "PROBE_TIMEOUT"


def test_probe_nonzero_exit_fails_closed(tmp_path: Path):
    fake_failing = tmp_path / "fake_fail.py"
    fake_failing.write_text(
        "import sys\n"
        "sys.stderr.write('Fatal crash on startup\\n')\n"
        "sys.exit(42)\n",
        encoding="utf-8",
    )
    fake_failing.chmod(fake_failing.stat().st_mode | stat.S_IEXEC | stat.S_IREAD)

    config = {"binaries": {"agy": str(fake_failing.resolve())}}
    res = detect_provider_cli("agy", config=config)

    assert not res.available
    assert "PROBE_NONZERO_EXIT: 42" in res.reason


def test_detect_all_providers_returns_all_allowlisted():
    results = detect_all_providers()
    assert "agy" in results
    assert "muse" in results
    assert isinstance(results["agy"], ProviderCapabilityInfo)
    assert isinstance(results["muse"], ProviderCapabilityInfo)


def test_cli_main_entrypoint(capsys):
    rc = main(["--json"])
    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "agy" in data
    assert "muse" in data
