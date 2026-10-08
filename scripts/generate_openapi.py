"""Regenerate static/openapi.json from server/app.py route decorators.

Anchored at the repository tree holding this script so it reads the real
app and writes the real spec regardless of the caller's working
directory. Importing this module has no side effects; call main().
"""
import re
import json
from pathlib import Path

ROUTE_PATTERN = re.compile(r'@app\.route\([\'"]([^\'"]+)[\'"](?:,\s*methods=\[([^\]]+)\])?\)')
REPO_ROOT = Path(__file__).resolve().parent.parent


def build_spec(app_code):
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

    for match in ROUTE_PATTERN.finditer(app_code):
        raw_path = match.group(1)
        methods_str = match.group(2)

        # Clean methods
        methods = ["GET"]
        if methods_str:
            methods = [m.strip(' "\'') for m in methods_str.split(',')]

        # Convert Flask <param> / <converter:param> to OpenAPI {param}.
        # The old pattern <[^:]*:?([^>]+)> let [^:]* greedily eat a plain
        # name, mangling <task_id> into {d}; the converter prefix must be
        # an all-or-nothing optional group instead.
        openapi_path = re.sub(r'<(?:[^:>]+:)?([^>]+)>', r'{\1}', raw_path)

        if openapi_path not in openapi["paths"]:
            openapi["paths"][openapi_path] = {}

        for method in methods:
            method = method.lower()
            openapi["paths"][openapi_path][method] = {
                "summary": f"Auto-generated {method.upper()} for {openapi_path}",
                "responses": {
                    "200": {"description": "OK"}
                }
            }
    return openapi


def main(root=None):
    base = Path(root) if root is not None else REPO_ROOT
    app_code = (base / "server" / "app.py").read_text(encoding="utf-8")
    openapi = build_spec(app_code)
    out_path = base / "static" / "openapi.json"
    out_path.write_text(json.dumps(openapi, indent=2), encoding="utf-8")
    print("OpenAPI spec regenerated with", len(openapi["paths"]), "paths.")
    return len(openapi["paths"])


if __name__ == "__main__":
    main()
