import sys
import json
from pathlib import Path

def route_memory(topic: str, workspace_path: str) -> list[str]:
    """
    Routes a given topic to the smallest authoritative memory set.
    """
    topic_normalized = topic.lower().strip()
    workspace = Path(workspace_path)
    
    # 1. Never route into public project memory for personal information
    personal_keywords = ["mother", "father", "personal information", "social security", "password"]
    if any(k in topic_normalized for k in personal_keywords):
        return []
    
    routed_files = set()
    
    # 2. Windows launcher -> Windows runtime canonical state
    if "windows launcher" in topic_normalized or "windows runtime" in topic_normalized:
        routed_files.add("memory/WINDOWS_VERIFICATION_LEDGER.md")
        routed_files.add("WINDOWS_PRODUCTIZATION_REPORT.md")
        
    # 3. Freeze incident -> recovery evidence
    if "freeze" in topic_normalized or "incident" in topic_normalized or "recovery" in topic_normalized:
        routed_files.add("CHIEF_BRAIN_STATE.md")
        routed_files.add("docs/COURIER_4_FORWARD_ONLY_OPERATING_CONTRACT.md")
        
    # 4. Marketing -> authority/grant memory
    if "marketing" in topic_normalized or "revenue" in topic_normalized:
        routed_files.add("docs/DEFERRED_PRODUCT_PLATFORM_AND_REVENUE_PLAYBOOK_2026-09-10.md")
        
    # 5. Fallback/Default Canonical Entry if nothing specific matched but it's project related
    if not routed_files:
        if "courier" in topic_normalized or "project" in topic_normalized:
            routed_files.add("CHIEF_BRAIN_STATE.md")
            
    # Return as list of strings, only if files actually exist in the workspace
    valid_files = []
    for f in routed_files:
        if (workspace / f).exists():
            valid_files.append(f)
            
    return sorted(valid_files)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python memory_router.py <topic> [workspace_path]")
        sys.exit(1)
        
    topic = sys.argv[1]
    workspace = sys.argv[2] if len(sys.argv) > 2 else "."
    
    files = route_memory(topic, workspace)
    print(json.dumps({"topic": topic, "authoritative_files": files}, indent=2))
