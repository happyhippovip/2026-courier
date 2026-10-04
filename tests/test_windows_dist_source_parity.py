"""Parity guard: committed Windows package Python layer must match source.

build_package.ps1 copies ``courier_worker/`` and ``adapters/`` verbatim into
``scripts/windows_worker/dist/`` and ``uv pip install``s the project into
``dist/libs``. If source changes without the package being refreshed, the
shipped worker silently runs stale code (observed: dist host.py lacked the
PID-reuse ``create_time`` identity fix). This test makes that drift visible.

It proves byte parity of the Python layer only; it is NOT Windows-native
runtime evidence and says nothing about Courier.exe or embedded Python.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "scripts" / "windows_worker" / "dist"

PAIRS = [
    (ROOT / "courier_worker", DIST / "courier_worker"),
    (ROOT / "courier_worker", DIST / "libs" / "courier_worker"),
    (ROOT / "adapters", DIST / "adapters"),
]


def _py_files(base: Path):
    return sorted(p.relative_to(base) for p in base.rglob("*.py")
                  if "__pycache__" not in p.parts)


@pytest.mark.parametrize("src,dst", PAIRS, ids=lambda p: str(p.relative_to(ROOT)))
def test_dist_python_layer_matches_source(src, dst):
    if not dst.exists():
        pytest.skip(f"{dst} not present in this checkout")
    drift = []
    for rel in _py_files(src):
        packaged = dst / rel
        if not packaged.exists():
            drift.append(f"missing: {rel}")
        elif packaged.read_bytes() != (src / rel).read_bytes():
            drift.append(f"differs: {rel}")
    assert not drift, (
        f"{dst.relative_to(ROOT)} is stale vs {src.relative_to(ROOT)}: {drift}. "
        "Refresh the package (build_package.ps1 or copy the Python layer)."
    )
