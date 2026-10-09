"""Tests for the ``courier_core/schemas`` contract files (P9-schemas).

Every ``*.schema.json`` under ``courier_core/schemas`` is a wire contract
read by scripts and workers. A malformed schema file would only surface when
a consumer tries to validate against it, so this module pins the structural
invariants all schema files currently satisfy:

* each file parses as JSON;
* each file declares a known draft (``$schema``), a non-empty ``title``,
  and either ``type: object`` or a composition keyword (``oneOf``/``$defs``);
* titles are unique across files (catches copy-paste of a whole file);
* every top-level ``required`` entry names a key of ``properties``;
* every ``$ref`` is a local fragment (``#/...``), so validation stays
  offline -- no network fetches;
* each file is valid against its declared draft meta-schema
  (``jsonschema`` is a declared project dependency).

Tests only; no behavior change.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema.validators import validator_for

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "courier_core" / "schemas"

KNOWN_DRAFTS = frozenset({
    "http://json-schema.org/draft-07/schema#",
    "https://json-schema.org/draft/2020-12/schema",
})


def _schema_files() -> list[Path]:
    return sorted(SCHEMAS_DIR.glob("*.schema.json"))


def _load(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, dict), f"{path.name}: top level must be an object"
    return data


def _walk_refs(node, found: list) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref":
                found.append(value)
            else:
                _walk_refs(value, found)
    elif isinstance(node, list):
        for item in node:
            _walk_refs(item, found)


def test_inventory_is_not_empty():
    """The schemas directory must contain contract files."""
    assert _schema_files(), f"no *.schema.json found in {SCHEMAS_DIR}"


@pytest.mark.parametrize("path", _schema_files(), ids=lambda p: p.name)
def test_file_parses_as_json_object(path: Path):
    """Every schema file must parse as a JSON object."""
    _load(path)


@pytest.mark.parametrize("path", _schema_files(), ids=lambda p: p.name)
def test_top_level_shape(path: Path):
    """Each schema declares a known draft, a title, and an object shape."""
    schema = _load(path)
    assert schema.get("$schema") in KNOWN_DRAFTS, (
        f"{path.name}: unknown $schema {schema.get('$schema')!r}"
    )
    title = schema.get("title")
    assert isinstance(title, str) and title.strip(), (
        f"{path.name}: title must be a non-empty string"
    )
    if "type" in schema:
        assert schema["type"] == "object", (
            f"{path.name}: top-level type must be 'object', got {schema['type']!r}"
        )
    else:
        assert "oneOf" in schema or "$defs" in schema, (
            f"{path.name}: schema without top-level type must compose via "
            "oneOf/$defs"
        )


def test_titles_unique():
    """Titles must be unique across files (catches whole-file copy-paste)."""
    titles = [(_load(p).get("title"), p.name) for p in _schema_files()]
    seen: dict[str, str] = {}
    for title, name in titles:
        assert title not in seen, (
            f"duplicate title {title!r} in {name} and {seen[title]}"
        )
        seen[title] = name


@pytest.mark.parametrize("path", _schema_files(), ids=lambda p: p.name)
def test_required_names_declared_properties(path: Path):
    """Every top-level required entry must name a declared property."""
    schema = _load(path)
    required = schema.get("required")
    properties = schema.get("properties")
    if isinstance(required, list) and isinstance(properties, dict):
        missing = [entry for entry in required if entry not in properties]
        assert not missing, (
            f"{path.name}: required entries missing from properties: {missing}"
        )


@pytest.mark.parametrize("path", _schema_files(), ids=lambda p: p.name)
def test_refs_are_local_fragments(path: Path):
    """All $refs must be local (#/...) so validation never needs network."""
    schema = _load(path)
    found: list = []
    _walk_refs(schema, found)
    remote = [ref for ref in found
              if not isinstance(ref, str) or not ref.startswith("#")]
    assert not remote, f"{path.name}: non-local $refs: {remote}"


@pytest.mark.parametrize("path", _schema_files(), ids=lambda p: p.name)
def test_valid_against_declared_draft(path: Path):
    """Each file must be valid against its declared draft meta-schema."""
    schema = _load(path)
    validator_for(schema).check_schema(schema)
