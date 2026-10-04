import json
import subprocess
import sys
import uuid
import datetime
from pathlib import Path

# Try importing revenue classes
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from courier_runtime.revenue import Lead, QUALIFIED
from courier_runtime.revenue_store import RevenueStore

def find_ci_pain_leads(home_dir: str):
    print("Searching GitHub for 'CI failing' issues in Python repos...")
    search_cmd = ["gh", "search", "issues", "CI failing", "language:python", "--state", "open", "--limit", "3", "--json", "repository,title,url,body"]
    res = subprocess.run(search_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Search failed", res.stderr)
        return
        
    issues = json.loads(res.stdout)
    store = RevenueStore(home_dir)
    
    leads_saved = 0
    for i, issue in enumerate(issues):
        repo = issue["repository"]["nameWithOwner"]
        url = issue["url"]
        
        # Determine specific pain
        body = issue.get("body", "")
        title = issue.get("title", "")
        problem = f"{title}. "
        if "ModuleNotFoundError" in body:
            problem += "Environment dependency missing (ModuleNotFoundError)."
        elif "AssertionError" in body:
            problem += "Product tests failing (AssertionError)."
        else:
            problem += "General CI failure reported."
            
        # Create lead
        lead_id = f"LD-AUTO-{datetime.datetime.now().strftime('%Y%m%d')}-{i+1}"
        lead = Lead(
            lead_id=lead_id,
            organisation=repo.split("/")[0],
            problem=problem,
            source=url,
            state=QUALIFIED,
            history=[{"from": "PROSPECT", "to": "QUALIFIED", "at": datetime.datetime.now().isoformat(), "approval": None, "note": "Auto-qualified from public issue search."}]
        )
        store.save_lead(lead)
        leads_saved += 1
        print(f"Saved lead {lead_id} for {repo}")
        
    print(f"Done. Saved {leads_saved} leads to {home_dir}/revenue/leads.jsonl")

if __name__ == "__main__":
    home = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent.parent)
    find_ci_pain_leads(home)
