import requests
import xml.etree.ElementTree as ET
import hashlib
from datetime import datetime
import json
import time

def fetch_decrypt(hub_url, token):
    url = 'https://decrypt.co/feed'
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    root = ET.fromstring(response.content)
    ns = {'dc': 'http://purl.org/dc/elements/1.1/', 'content': 'http://purl.org/rss/1.0/modules/content/'}
    
    for item in root.findall('.//item'):
        title = item.find('title').text
        link = item.find('link').text
        pub_date = item.find('pubDate').text
        
        creator = item.find('dc:creator', ns)
        author = creator.text if creator is not None else "Unknown"
        
        content_encoded = item.find('content:encoded', ns)
        description = item.find('description')
        content_text = content_encoded.text if content_encoded is not None else (description.text if description is not None else "")
        
        article_id = hashlib.sha256(link.encode('utf-8')).hexdigest()
        
        article = {
            "article_id": article_id,
            "source_id": "decrypt",
            "title": title,
            "url": link,
            "published_at": pub_date,
            "author": author,
            "content_text": content_text,
            "metadata": {}
        }
        
        payload = {
            "adapter": "local_json_delivery",
            "effect_class": "idempotent",
            "max_attempts": 3,
            "lease_ttl_s": 60,
            "params": article,
            "idempotency_key": f"decrypt:{article_id}"
        }
        
        try:
            res = requests.post(f"{hub_url}/v1/tasks", json=payload, headers={"X-Courier-Token": token})
            if res.status_code == 201:
                print(f"Created task for {article_id}")
            elif res.status_code == 200:
                print(f"Skipped duplicate {article_id}")
            else:
                print(f"Error {res.status_code}: {res.text}")
        except Exception as e:
            print(f"Failed to post task: {e}")

if __name__ == '__main__':
    import os
    import sys
    from pathlib import Path
    
    hub_url = os.environ.get("COURIER_HUB_URL", "http://127.0.0.1:8080")
    token = os.environ.get("COURIER_HUB_TOKEN")
    if not token:
        home_env = os.environ.get("COURIER_HOME")
        if home_env:
            base = Path(home_env)
        else:
            pd = os.environ.get("LOCALAPPDATA")
            base = (Path(pd) if pd else Path.home() / ".courier") / "Courier"
            
        token_path = base / "run" / "controller.token"
        if token_path.exists():
            token = token_path.read_text().strip()
        else:
            print("No token found")
            sys.exit(1)
            
    fetch_decrypt(hub_url, token)
