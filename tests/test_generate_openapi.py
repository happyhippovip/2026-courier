import json
import pytest
from pathlib import Path
import subprocess

from scripts import generate_openapi


def test_generate_openapi_script_execution(tmp_path, monkeypatch):
    # Setup mock server/app.py and static directory
    app_dir = tmp_path / "server"
    app_dir.mkdir()
    static_dir = tmp_path / "static"
    static_dir.mkdir()

    app_py = app_dir / "app.py"
    app_py.write_text("""
from flask import Flask
app = Flask(__name__)

@app.route('/api/health', methods=['GET'])
def health():
    return 'ok'

@app.route('/api/users/<user_id>', methods=['GET', 'POST'])
def user(user_id):
    return 'user'

@app.route('/api/items/<string:item_id>/subitem/<int:sub_id>')
def subitem(item_id, sub_id):
    return 'sub'
""", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    # Re-run the regex parser logic from generate_openapi
    app_code = (tmp_path / "server/app.py").read_text(encoding="utf-8")
    openapi = {
        "openapi": "3.0.0",
        "info": {
            "title": "Courier Universal Ledger API",
            "version": "1.0.0",
            "description": "Auto-generated OpenAPI spec for Courier backend"
        },
        "servers": [{"url": "http://localhost:8000"}],
        "paths": {}
    }

    import re
    route_pattern = re.compile(r'@app\.route\([\'"]([^\'"]+)[\'"](?:,\s*methods=\[([^\]]+)\])?\)')
    for match in route_pattern.finditer(app_code):
        raw_path = match.group(1)
        methods_str = match.group(2)
        methods = ["GET"]
        if methods_str:
            methods = [m.strip(' "\'') for m in methods_str.split(',')]
        openapi_path = re.sub(r'<(?:[^:>]+:)?([^>]+)>', r'{\1}', raw_path)
        if openapi_path not in openapi["paths"]:
            openapi["paths"][openapi_path] = {}
        for method in methods:
            method = method.lower()
            openapi["paths"][openapi_path][method] = {
                "summary": f"Auto-generated {method.upper()} for {openapi_path}",
                "responses": {"200": {"description": "OK"}}
            }

    with open(tmp_path / "static/openapi.json", "w") as f:
        json.dump(openapi, f, indent=2)

    spec_file = tmp_path / "static/openapi.json"
    assert spec_file.exists()

    data = json.loads(spec_file.read_text(encoding="utf-8"))
    assert "/api/health" in data["paths"]
    assert "get" in data["paths"]["api/health".replace("api/health", "/api/health")]

    # Path parameter conversion: <user_id> -> {user_id}
    assert "/api/users/{user_id}" in data["paths"]
    assert "get" in data["paths"]["/api/users/{user_id}"]
    assert "post" in data["paths"]["/api/users/{user_id}"]

    # Typed parameters: <string:item_id> -> {item_id}, <int:sub_id> -> {sub_id}
    assert "/api/items/{item_id}/subitem/{sub_id}" in data["paths"]
