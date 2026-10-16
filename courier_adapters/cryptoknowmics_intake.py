import requests
import hashlib
import json
import os
import sys
from pathlib import Path
from html.parser import HTMLParser

class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs= True
        self.text = []
    def handle_data(self, d):
        self.text.append(d)
    def get_data(self):
        return ''.join(self.text)

def remove_tags(html):
    if not html:
        return ""
    s = HTMLStripper()
    s.feed(html)
    return s.get_data().strip()

def fetch_cryptoknowmics(hub_url, token):
    url = 'https://www.cryptoknowmics.com/ct/v5/news/news-details'
    headers = {
        'Content-Type': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Origin': 'https://www.cryptoknowmics.com',
        'Referer': 'https://www.cryptoknowmics.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'
    }
    payload = {"slug": "cryptocurrency-news", "start": 0, "limit": 6}
    
    response = requests.post(url, headers=headers, json=payload, timeout=10)
    response.raise_for_status()
    
    data = response.json()
    posts = data.get('responseData', [])
    if len(posts) > 2:
        posts = posts[2]
    else:
        print("No posts found in response")
        return
        
    for post in posts:
        _id = post.get('id')
        title = post.get('post_title') or ""
        post_content = post.get('post_description') or ""
        date = post.get('post_date') or ""
        author_first = post.get('first_name') or ""
        author_last = post.get('last_name') or ""
        author = f"{author_first} {author_last}".strip() or "Unknown"
        slug = post.get('slug')
        link = f'https://www.cryptoknowmics.com/news/{slug}' if slug else f'https://www.cryptoknowmics.com/news/{_id}'
        
        content_text = remove_tags(post_content)
        article_id = hashlib.sha256(link.encode('utf-8')).hexdigest()
        
        article = {
            "article_id": article_id,
            "source_id": "cryptoknowmics",
            "title": title,
            "url": link,
            "published_at": date,
            "author": author,
            "content_text": content_text,
            "metadata": {"original_id": _id}
        }
        
        # In Phase 3, we can route it to any adapter. We will still just use local_json_delivery for now, 
        # or maybe we should use telegram_delivery if we want to send it directly? Let's use local_json_delivery for parity.
        task_payload = {
            "adapter": "local_json_delivery",
            "effect_class": "idempotent",
            "max_attempts": 3,
            "lease_ttl_s": 60,
            "params": article,
            "idempotency_key": f"cryptoknowmics:{article_id}"
        }
        
        try:
            res = requests.post(f"{hub_url}/v1/tasks", json=task_payload, headers={"X-Courier-Token": token})
            if res.status_code == 201:
                print(f"Created task for {article_id}")
            elif res.status_code == 200:
                print(f"Skipped duplicate {article_id}")
            else:
                print(f"Error {res.status_code}: {res.text}")
        except Exception as e:
            print(f"Failed to post task: {e}")

if __name__ == '__main__':
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
            
    fetch_cryptoknowmics(hub_url, token)
