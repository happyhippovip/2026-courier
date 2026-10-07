"""Decrypt source adapter."""

import json
import os
import urllib.request
import urllib.error
from dataclasses import dataclass

@dataclass
class RunResult:
    outcome: str
    reason: str = ""
    retryable: bool = False

def run(params: dict, workdir: str, attempt: int) -> RunResult:
    """Fetch a single Decrypt article and normalize it."""
    url = params.get("url")
    if not url:
        return RunResult("failure", "missing url", retryable=False)
    
    # We expect params to include the pre-parsed metadata from the RSS feed,
    # or at least the URL to fetch the full article. 
    # For Phase 1, we simulate fetching the detail page if needed, or just 
    # normalize the passed data.
    
    # In a real implementation we would fetch `url` here and parse HTML.
    # To keep this idempotent and isolated, we will just normalize what we get
    # or make a simple request if we must.
    
    # Let's try to fetch if we must, but if params has the content, we just use it.
    title = params.get("title", "")
    author = params.get("author", "Decrypt Staff")
    published_at = params.get("published_at", "")
    content_text = params.get("content_text", "")
    
    if not content_text and url:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8')
                # A very crude extraction for demonstration purposes.
                # In reality we'd parse the __NEXT_DATA__ JSON.
                if '__NEXT_DATA__' in html:
                    content_text = "Extracted from NEXT_DATA"
                else:
                    content_text = html[:1000]
        except Exception as e:
            return RunResult("failure", f"fetch failed: {e}", retryable=True)

    article_id = params.get("article_id", "unknown")
    
    canonical = {
        "id": f"decrypt-{article_id}",
        "source": "decrypt",
        "title": title,
        "url": url,
        "author": author,
        "published_at": published_at,
        "content_text": content_text
    }
    
    out_path = os.path.join(workdir, "article.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(canonical, f, indent=2)
        
    # Atomic rename/fsync is handled by the worker host / Courier, 
    # but we just need to produce the file in workdir.
    
    return RunResult("success")

def verify(task, result, home: str):
    """Verify the produced artifact matches the canonical schema."""
    artifacts = result.payload.get("artifacts", [])
    if not artifacts:
        return "reject", "no artifacts produced", False
        
    import json
    import os
    
    for artifact in artifacts:
        path = os.path.join(home, artifact["path"])
        if not os.path.exists(path):
            return "reject", f"missing artifact {artifact['path']}", False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # Verify schema
            required = {"id", "source", "title", "url", "author", "published_at", "content_text"}
            if not required.issubset(data.keys()):
                return "reject", f"missing required fields in canonical schema: {required - data.keys()}", False
                
            if data["source"] != "decrypt":
                return "reject", "invalid source", False
                
        except json.JSONDecodeError:
            return "reject", "artifact is not valid JSON", False
            
    return "accept", "article verified", False
