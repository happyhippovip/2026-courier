import re
import json
import os

with open("server/app.py", "r") as f:
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
    
    # Convert Flask <param> or <type:param> to OpenAPI {param}
    openapi_path = re.sub(r'<(?:[^:]+:)?([^>]+)>', r'{\1}', raw_path)
    
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

with open("static/openapi.json", "w") as f:
    json.dump(openapi, f, indent=2)

print("OpenAPI spec regenerated with", len(openapi["paths"]), "paths.")
