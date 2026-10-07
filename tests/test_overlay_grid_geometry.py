"""W11 grid-geometry pin: calculate_grid covers 12/14/16 profiles.

Acceptance source: docs/v1/W14_OVERLAY_ACCEPTANCE_MATRIX.md §2 —
geometry must pass the 12, 14 and 16 profile grids. Before this file no
test exercised calculate_grid at all (only the state machine fold and a
mocked renderer integration were covered), so a cols/rows regression or
a changed supported-set would have shipped silently.

Contract pinned (invariants, not implementation details):
- one rect per profile for 12, 14 and 16;
- every cell contained in the usable rect (no overflow);
- cells never overlap (edge-touching allowed);
- uniform cell size within a grid;
- anything outside {12, 14, 16} raises ValueError.
"""

import pytest

from courier_overlay.layout_engine import LayoutEngine, Rect, Screen, WindowAdapter


class _DummyAdapter(WindowAdapter):
    def get_screen(self):
        return Screen(800, 600, Rect(0, 0, 800, 600))

    def list_windows(self):
        return []

    def move_window(self, wid, rect):
        return True


SCREEN = Screen(800, 600, Rect(0, 0, 800, 600))


def _engine():
    return LayoutEngine(_DummyAdapter())


def _overlaps(a: Rect, b: Rect) -> bool:
    return (
        a.x < b.x + b.width
        and b.x < a.x + a.width
        and a.y < b.y + b.height
        and b.y < a.y + a.height
    )


@pytest.mark.parametrize("profiles", [12, 14, 16])
def test_grid_yields_exact_profile_count(profiles):
    rects = _engine().calculate_grid(SCREEN, profiles)
    assert len(rects) == profiles


@pytest.mark.parametrize("profiles", [12, 14, 16])
def test_grid_cells_contained_uniform_non_overlapping(profiles):
    rects = _engine().calculate_grid(SCREEN, profiles)
    usable = SCREEN.usable_rect
    for r in rects:
        assert r.width > 0 and r.height > 0
        assert r.x >= usable.x and r.y >= usable.y
        assert r.x + r.width <= usable.x + usable.width
        assert r.y + r.height <= usable.y + usable.height
    sizes = {(r.width, r.height) for r in rects}
    assert len(sizes) == 1
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            assert not _overlaps(rects[i], rects[j])


@pytest.mark.parametrize("profiles", [0, 1, 11, 13, 15, 17, 100, -4])
def test_grid_rejects_unsupported_profile_counts(profiles):
    with pytest.raises(ValueError):
        _engine().calculate_grid(SCREEN, profiles)
