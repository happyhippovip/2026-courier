import json
import re
from pathlib import Path

import pytest

ROUTE_PATTERN = re.compile(r'@app\.route\([\'"]([^\'"]+)[\'"](?:,\s*methods=\[([^\]]+)\])?\)')


def parse_app_routes(app_code: str) -> dict:
    openapi = {
        "openapi": "3.0.0",
        "info": {
            "title": "Courier Universal Ledger API",
            "version": "1.0.0",
            "description": "Auto-generated OpenAPI spec for Courier backend",
        },
        "servers": [{"url": "http://localhost:8000"}],
        "paths": {},
    }

    for match in ROUTE_PATTERN.finditer(app_code):
        raw_path = match.group(1)
        methods_str = match.group(2)

        methods = ["GET"]
        if methods_str:
            methods = [m.strip(' "\'') for m in methods_str.split(",")]

        # Convert Flask <param> or <type:param> to OpenAPI {param}
        openapi_path = re.sub(r"<(?:[^:]+:)?([^>]+)>", r"{\1}", raw_path)

        if openapi_path not in openapi["paths"]:
            openapi["paths"][openapi_path] = {}

        for method in methods:
            method = method.lower()
            openapi["paths"][openapi_path][method] = {
                "summary": f"Auto-generated {method.upper()} for {openapi_path}",
                "responses": {"200": {"description": "OK"}},
            }
    return openapi


def test_route_pattern_conversions():
    sample_code = """
@app.route("/")
def index(): pass

@app.route("/items/<int:item_id>", methods=["GET", "DELETE"])
def item(item_id): pass

@app.route("/files/<path:filepath>")
def file(filepath): pass

@app.route("/users/<username>", methods=['POST'])
def create_user(username): pass
"""
    spec = parse_app_routes(sample_code)
    paths = spec["paths"]

    assert "/" in paths
    assert "get" in paths["/"]

    assert "/items/{item_id}" in paths
    assert "get" in paths["/items/{item_id}"]
    assert "delete" in paths["/items/{item_id}"]

    assert "/files/{filepath}" in paths
    assert "get" in paths["/files/{filepath}"]

    assert "/users/{username}" in paths
    assert "post" in paths["/users/{username}"]


def test_openapi_schema_structure_and_drift():
    repo_root = Path(__file__).resolve().parent.parent
    app_path = repo_root / "server/app.py"
    spec_path = repo_root / "static/openapi.json"

    assert app_path.exists(), "server/app.py must exist"
    assert spec_path.exists(), "static/openapi.json must exist"

    app_code = app_path.read_text(encoding="utf-8")
    generated = parse_app_routes(app_code)
    committed = json.loads(spec_path.read_text(encoding="utf-8"))

    # Verify basic OpenAPI contract
    assert committed["openapi"] == "3.0.0"
    assert committed["info"]["title"] == "Courier Universal Ledger API"
    assert len(committed["paths"]) == 22

    # Critical endpoints must be declared
    for endpoint in ["/health", "/status", "/tasks/claim", "/tasks/result", "/goals", "/api/state"]:
        assert endpoint in committed["paths"], f"Endpoint {endpoint} missing from openapi.json"

    # Verify parameter naming accuracy
    assert "/goals/{goal_id}" in committed["paths"]
    assert "/tasks/{task_id}/resume" in committed["paths"]

    # Verify no drift in endpoint coverage between server/app.py and committed spec
    assert set(generated["paths"].keys()) == set(committed["paths"].keys())
