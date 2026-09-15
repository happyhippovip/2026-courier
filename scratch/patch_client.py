with open("social_platform/client/client.py", "r") as f:
    text = f.read()

get_genesis_method = """    def get_genesis_registry(self):
        res = self._request("GET", "/pow001/registry")
        return res.get("blocks", {})

    def reserve_genesis_block(self, company_name, logo_url):
        return self._request("POST", "/pow001/reserve", data={"company_name": company_name, "logo_url": logo_url})

    def get_all_communities(self) -> List[Dict[str, Any]]:"""

if "get_genesis_registry" not in text:
    text = text.replace("    def get_all_communities(self) -> List[Dict[str, Any]]:", get_genesis_method)
    with open("social_platform/client/client.py", "w") as f:
        f.write(text)
