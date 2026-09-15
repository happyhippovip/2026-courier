with open("social_platform/api/server.py", "r") as f:
    text = f.read()

# Add GET route
get_route = """        # /pow001/registry
        elif path_parts[0] == "pow001" and len(path_parts) == 2 and path_parts[1] == "registry":
            return self._send_json({"status": "success", "blocks": get_genesis_registry()})

        # /communities/..."""
if "pow001/registry" not in text:
    text = text.replace("        # /communities/...", get_route)

# Add POST route
post_route = """        # POST /pow001/reserve
        elif path_parts[0] == "pow001" and len(path_parts) == 2 and path_parts[1] == "reserve":
            return self._send_json(reserve_block(body.get("company_name", "Anonymous"), body.get("logo_url", "")))

        # POST /communities"""
if "pow001/reserve" not in text:
    text = text.replace("        # POST /communities", post_route)

with open("social_platform/api/server.py", "w") as f:
    f.write(text)
