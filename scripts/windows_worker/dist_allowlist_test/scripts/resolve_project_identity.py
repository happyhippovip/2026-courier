import os
import sys
import json
import re
from pathlib import Path

def resolve_project_identity(query: str, workspace_path: str = None) -> dict:
    """
    Given a vague query (e.g., 'Courier Symphony', 'my project') and an optional workspace path,
    resolves and returns the canonical project identity.
    """
    if workspace_path is None:
        workspace_path = os.getcwd()
    
    workspace = Path(workspace_path)
    
    canonical_identity = {
        "canonical_name": None,
        "repo_name": None,
        "is_courier": False,
        "confidence": 0,
        "evidence": []
    }

    # 1. Check workspace directory name
    repo_name = workspace.name
    canonical_identity["repo_name"] = repo_name
    if "courier" in repo_name.lower():
        canonical_identity["is_courier"] = True
        canonical_identity["confidence"] += 10
        canonical_identity["evidence"].append(f"Directory name implies courier: {repo_name}")
        canonical_identity["canonical_name"] = "Courier Symphony"

    # 2. Check pyproject.toml
    pyproject_path = workspace / "pyproject.toml"
    if pyproject_path.exists():
        content = pyproject_path.read_text(encoding="utf-8")
        if re.search(r'name\s*=\s*"courier"', content, re.IGNORECASE):
            canonical_identity["is_courier"] = True
            canonical_identity["confidence"] += 40
            canonical_identity["evidence"].append("pyproject.toml defines name='courier'")
            canonical_identity["canonical_name"] = "Courier Symphony"

    # 3. Check CHIEF_BRAIN_STATE.md (Canonical Memory)
    brain_state_path = workspace / "CHIEF_BRAIN_STATE.md"
    if brain_state_path.exists():
        content = brain_state_path.read_text(encoding="utf-8")
        if "COURIER" in content:
            canonical_identity["is_courier"] = True
            canonical_identity["confidence"] += 30
            canonical_identity["evidence"].append("CHIEF_BRAIN_STATE.md contains 'COURIER'")
            canonical_identity["canonical_name"] = "Courier Symphony"

    # 4. Check git remote (if we wanted to parse .git/config, but standard check is enough)
    git_config_path = workspace / ".git" / "config"
    if git_config_path.exists():
        content = git_config_path.read_text(encoding="utf-8", errors="ignore")
        if "courier" in content.lower():
            canonical_identity["is_courier"] = True
            canonical_identity["confidence"] += 20
            canonical_identity["evidence"].append(".git/config contains 'courier'")
            canonical_identity["canonical_name"] = "Courier Symphony"

    # Match query against resolved canonical
    query_normalized = query.lower().strip()
    vague_terms = ["my project", "courier", "courier symphony", "2026-courier", "windows project", "the project"]
    
    if query_normalized in vague_terms and canonical_identity["is_courier"]:
        canonical_identity["confidence"] += 10
        canonical_identity["evidence"].append(f"Query '{query}' maps to known vague term for this canonical project.")
        
    return canonical_identity

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = sys.argv[1]
    else:
        query = "my project"
        
    workspace_path = sys.argv[2] if len(sys.argv) > 2 else None
        
    identity = resolve_project_identity(query, workspace_path)
    print(json.dumps(identity, indent=2))
