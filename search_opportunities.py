import urllib.request
import json
import xml.etree.ElementTree as ET

def fetch_hn():
    try:
        url = "https://hacker-news.firebaseio.com/v0/item/39562986.json" # Random popular post, but let's just get topstories
        req = urllib.request.urlopen("https://hacker-news.firebaseio.com/v0/topstories.json")
        stories = json.loads(req.read())[:10]
        titles = []
        for s in stories:
            req = urllib.request.urlopen(f"https://hacker-news.firebaseio.com/v0/item/{s}.json")
            item = json.loads(req.read())
            titles.append(item.get("title", ""))
        return titles
    except Exception as e:
        return str(e)

def search_upwork():
    # Upwork requires auth for API, but let's just fetch a public RSS feed for Python or Automation
    try:
        url = "https://www.upwork.com/ab/feed/jobs/rss?q=automation&sort=recency"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req)
        root = ET.fromstring(response.read())
        jobs = []
        for item in root.findall('./channel/item')[:10]:
            jobs.append(item.find('title').text)
        return jobs
    except Exception as e:
        return str(e)

print("HN:", fetch_hn())
print("Upwork:", search_upwork())
