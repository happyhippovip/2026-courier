import re
import json
import os
from pathlib import Path

def _refuse_symlink(path: Path) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("refusing to follow a symlink")

_app_path = Path("server/app.py")
_output_path = Path("static/openapi.json")
_refuse_symlink(_app_path)
_refuse_symlink(_output_path)

with open(_app_path, "r") as f:
    app_code = f.read()

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

# Regex to find all @app.route
route_pattern = re.compile(r'@app\.route\([\'"]([^\'"]+)[\'"](?:,\s*methods=\[([^\]]+)\])?\)')

for match in route_pattern.finditer(app_code):
    raw_path = match.group(1)
    methods_str = match.group(2)
    
    # Clean methods
    methods = ["GET"]
    if methods_str:
        methods = [m.strip(' "\'') for m in methods_str.split(',')]
    
    # Convert Flask <param> to OpenAPI {param}
    openapi_path = re.sub(r'<[^:]*:?([^>]+)>', r'{\1}', raw_path)
    
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

_refuse_symlink(_output_path)
with open(_output_path, "w") as f:
    json.dump(openapi, f, indent=2)

print("OpenAPI spec regenerated with", len(openapi["paths"]), "paths.")
