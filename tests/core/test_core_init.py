"""L4 hardening: courier_core package init stays minimal and versioned.

courier_core/__init__.py owns only the package docstring and __version__.
These tests pin that contract: the version is present and well-formed, it
matches pyproject.toml, the import stays lightweight (no heavy submodule
imports), and build_identity() reports the same version.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import courier_core
from courier_core import __version__ as CORE_VERSION

REPO_ROOT = Path(__file__).resolve().parents[2]
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(\.[a-z0-9]+)?$")


def test_version_attribute_is_string():
    assert isinstance(courier_core.__version__, str)
    assert isinstance(CORE_VERSION, str)
    assert courier_core.__version__ == CORE_VERSION


def test_version_is_well_formed():
    assert CORE_VERSION
    assert len(CORE_VERSION) <= 50
    assert _VERSION_RE.match(CORE_VERSION), f"unexpected version shape: {CORE_VERSION!r}"


def test_version_matches_pyproject():
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r"^version\s*=\s*\"([^\"]+)\"", text, re.M)
    assert match is not None, "pyproject.toml must declare a version"
    assert match.group(1) == CORE_VERSION


def test_package_docstring_present():
    assert isinstance(courier_core.__doc__, str)
    assert courier_core.__doc__.strip()


def test_import_stays_lightweight():
    code = (
        "import sys, courier_core; "
        "print(','.join(sorted(m for m in sys.modules if m.startswith('courier_core'))))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr[-500:]
    assert proc.stdout.strip() == "courier_core"


def test_build_identity_reports_same_version():
    from courier_core.build import build_identity

    identity = build_identity()
    assert identity["version"] == CORE_VERSION


def test_reimport_is_stable():
    import importlib

    first = courier_core.__version__
    importlib.reload(courier_core)
    try:
        assert courier_core.__version__ == first
    finally:
        importlib.reload(courier_core)
