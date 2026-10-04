"""The desktop JS tests run against a fixture produced by the real model."""

import json
from pathlib import Path

from fixture_source import build

FIXTURE = Path(__file__).resolve().parents[1] / "desktop" / "fixtures" / "home_view.json"


def test_desktop_fixture_matches_the_projection_model():
    assert json.loads(FIXTURE.read_text(encoding="utf-8")) == json.loads(json.dumps(build())), (
        "regenerate: python -c 'import json,sys; sys.path[:0]=[\"tests/hub\"]; "
        "from fixture_source import build; print(json.dumps(build(), indent=2))' > tests/desktop/fixtures/home_view.json")
