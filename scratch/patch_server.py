with open("social_platform/api/server.py", "r") as f:
    text = f.read()

# Fix import
text = text.replace("from social_platform.api.pow001_sponsorship import reserve_block, get_genesis_registry\n", "")
text = "from social_platform.api.pow001_sponsorship import reserve_block, get_genesis_registry\n" + text

# Add GET route
get_route = """        if parsed.path == "/communities":
            return self._send_json({"communities": [c.to_dict() for c in DB.communities.values()]})
        
        if parsed.path == "/pow001/registry":
            return self._send_json({"status": "success", "blocks": get_genesis_registry()})
"""
if "/pow001/registry" not in text:
    text = text.replace('        if parsed.path == "/communities":\n            return self._send_json({"communities": [c.to_dict() for c in DB.communities.values()]})', get_route)

# Add POST route
post_route = """        # POST /users
        if parsed.path == "/pow001/reserve":
            return self._send_json(reserve_block(body.get("company_name", "Anonymous"), body.get("logo_url", "")))

        if parsed.path == "/users":"""
if "/pow001/reserve" not in text:
    text = text.replace('        # POST /users\n        if parsed.path == "/users":', post_route)

with open("social_platform/api/server.py", "w") as f:
    f.write(text)
