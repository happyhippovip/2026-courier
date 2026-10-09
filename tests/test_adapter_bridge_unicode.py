"""P9 hardening for courier_worker.adapter_bridge: unicode dispatch-ID pins.

The open bridge-hardening PRs (#315 general, #354 edge paths, #363
pure-unit, #369 fail-closed) pin ASCII separators, empty IDs, the
allowlist, size bounds and report shapes with example cases. This file
deliberately covers only the seam none of them exercises: how non-ASCII
dispatch IDs flow through ``_safe()`` into the host-owned request/report
paths, and the contrast with effect keys, which ``EFFECT_KEY_RE``
restricts to ASCII.

Scope: tests only, no behavior change. Local tmp fixtures only
(no network, no credentials, no subprocesses).
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from courier_worker import adapter_bridge as B
from courier_worker.host import SpecError


def test_safe_preserves_unicode_letters():
    assert B._safe("héllo-世界-01") == "héllo-世界-01"


def test_safe_preserves_unicode_digits():
    assert B._safe("job-١٢٣") == "job-١٢٣"


@pytest.mark.parametrize("raw,expected", [
    ("a😀b", "a_b"),
    ("a\x00b", "a_b"),
    ("a/b\\c", "a_b_c"),
    ("a b\tc", "a_b_c"),
    ("café/tâche", "café_tâche"),
])
def test_safe_replaces_non_alnum_with_underscore(raw, expected):
    assert B._safe(raw) == expected


def test_request_and_report_paths_carry_unicode_id(tmp_path):
    home = str(tmp_path)
    assert B.request_path(home, "déploiement-01") == os.path.join(
        home, "run", "requests", "déploiement-01.json")
    assert B.report_path(home, "déploiement-01") == os.path.join(
        home, "run", "reports", "déploiement-01.json")


@pytest.mark.parametrize("bad_key", ["café", "deploy-日本", "emoji-😀"])
def test_effect_key_rejects_non_ascii(bad_key):
    spec = {"adapter": "synthetic", "params": {"write": "pinned.txt"},
            "effect_key": bad_key}
    with pytest.raises(SpecError):
        B.validate_request(spec)


def test_validate_request_accepts_ascii_effect_key_control():
    adapter, params, effect_key = B.validate_request(
        {"adapter": "synthetic", "params": {"write": "pinned.txt"},
         "effect_key": "run-01_ok"})
    assert (adapter, params, effect_key) == (
        "synthetic", {"write": "pinned.txt"}, "run-01_ok")


def _spec(home, dispatch_id):
    return SimpleNamespace(
        adapter="synthetic", params={"write": "unicode-out.txt"}, attempt=1,
        task_id="task-unicode-1", dispatch_id=dispatch_id,
        effect_key="run-unicode-01", artifact_dir=os.path.join(home, "artifacts"))


def test_write_request_roundtrip_with_unicode_dispatch(tmp_path):
    home = str(tmp_path)
    spec = _spec(home, "tâche-日本-01")
    path = B.write_request(home, spec)
    assert path == B.request_path(home, "tâche-日本-01")
    with open(path, encoding="utf-8") as handle:
        body = json.load(handle)
    assert body["adapter"] == "synthetic"
    assert body["dispatch_id"] == "tâche-日本-01"
    assert body["report"] == B.report_path(home, "tâche-日本-01")
    # No report has been produced yet, and cleanup removes the request.
    assert B.read_report(home, "tâche-日本-01") is None
    B.cleanup(home, "tâche-日本-01")
    assert not os.path.exists(path)
    B.cleanup(home, "tâche-日本-01")  # idempotent


def test_runner_argv_uses_sanitized_unicode_name(tmp_path):
    import sys

    home = str(tmp_path)
    argv = B.runner_argv(home, "a/b😀c")
    assert argv == (sys.executable, B.RUNNER_SCRIPT,
                    B.request_path(home, "a/b😀c"))
    assert argv[2].endswith(os.path.join("run", "requests", "a_b_c.json"))
