"""P9 test hardening for courier_core init (version + docstring pins).

Tests only; no behavior change. Pins the package version contract used by
courier_core.build build_identity(): non-empty string, numeric dotted core,
no whitespace or path-like characters, stable across reads, and a present
package docstring. No network, no credentials, no filesystem writes.
"""

import re

import courier_core
from courier_core import build as _build

_NUMERIC_CORE = re.compile(r"^\d+\.\d+\.\d+")


def test_version_is_nonempty_string():
    assert isinstance(courier_core.__version__, str)
    assert courier_core.__version__ != ""


def test_version_has_numeric_dotted_core():
    assert _NUMERIC_CORE.match(courier_core.__version__) is not None


def test_version_has_no_surrounding_whitespace():
    version = courier_core.__version__
    assert version == version.strip()


def test_version_has_no_path_or_host_chars():
    version = courier_core.__version__
    for banned in (" ", "/", "\\", "@", ":"):
        assert banned not in version


def test_version_is_not_placeholder():
    assert courier_core.__version__.lower() not in {"unknown", "undefined", "none", "0.0.0"}


def test_version_stable_across_reads():
    assert courier_core.__version__ == courier_core.__version__


def test_package_docstring_present():
    assert isinstance(courier_core.__doc__, str)
    assert courier_core.__doc__.strip() != ""


def test_build_identity_tracks_package_version(monkeypatch):
    monkeypatch.delenv(_build.BUILD_ID_ENV, raising=False)
    assert _build.build_identity()["version"] == courier_core.__version__
