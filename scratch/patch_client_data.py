with open("social_platform/client/client.py", "r") as f:
    text = f.read()

text = text.replace('self._request("POST", "/pow001/reserve", json={"company_name": company_name, "logo_url": logo_url})', 'self._request("POST", "/pow001/reserve", json_data={"company_name": company_name, "logo_url": logo_url})')

with open("social_platform/client/client.py", "w") as f:
    f.write(text)
