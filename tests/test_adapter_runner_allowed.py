"""P9 allowlist pins for courier_worker.adapter_runner (tests only).

Covers only the closed-adapter contract in courier_worker/adapter_runner.py:

- ``ALLOWED`` is exactly ``frozenset({"synthetic"})`` (closed: adding an
  adapter is a code change);
- it is an immutable frozenset (not a list/set/dict), hashable, with one
  lowercase entry;
- membership is exact and case-sensitive (no network, no subprocess,
  no filesystem writes).

No behavior change. No network calls. No credentials. Unlike the
request-validation pins (exit-2/3/0 via ``main()``), these tests never
call ``main()`` and never touch request/report files.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import courier_worker.adapter_runner as runner_mod
from courier_worker.adapter_runner import ALLOWED

_ADAPTER_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def test_allowed_is_exact_singleton():
    assert ALLOWED == frozenset({"synthetic"})
    assert len(ALLOWED) == 1


def test_allowed_is_immutable_frozenset():
    assert isinstance(ALLOWED, frozenset)
    assert not isinstance(ALLOWED, (list, set, dict, tuple))
    # frozenset has no mutators; set does.
    for mutator in ("add", "discard", "pop", "remove", "clear", "update"):
        assert not hasattr(ALLOWED, mutator), mutator
    # Hashable so it can be used as a mapping key / in sets.
    assert hash(ALLOWED) == hash(frozenset({"synthetic"}))


def test_allowed_elements_are_valid_adapter_names():
    for entry in ALLOWED:
        assert isinstance(entry, str)
        assert entry
        assert _ADAPTER_NAME_RE.match(entry), entry


def test_allowed_membership_is_exact_and_case_sensitive():
    assert "synthetic" in ALLOWED
    for other in ("Synthetic", "SYNTHETIC", "", "synthetic ", " synthetic",
                  "local_shell", "evil", "synthetic2"):
        assert other not in ALLOWED
    assert None not in ALLOWED
    assert 123 not in ALLOWED


def test_allowed_union_does_not_mutate():
    before = frozenset(ALLOWED)
    assert (ALLOWED | {"evil"}) == frozenset({"synthetic", "evil"})
    assert ALLOWED == before


def test_reimport_gives_same_allowed_object():
    import importlib

    reloaded = importlib.import_module("courier_worker.adapter_runner")
    assert reloaded is runner_mod
    assert reloaded.ALLOWED is ALLOWED
    assert reloaded.ALLOWED == frozenset({"synthetic"})


def test_module_exposes_allowed_as_documented():
    assert hasattr(runner_mod, "ALLOWED")
    assert runner_mod.ALLOWED is ALLOWED


def test_runner_package_root_on_sys_path():
    # The runner is started by path, so it inserts the package root into
    # sys.path instead of trusting the inherited environment.
    expected = str(Path(runner_mod.__file__).resolve().parents[1])
    assert expected in sys.path
