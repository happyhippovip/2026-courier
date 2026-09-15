from pathlib import Path
import re

p = Path("scripts/router_dispatch_codex.py")
code = p.read_text()

replacement = """
    queue = OpportunityQueue(repo_dir=COURIER_DIR)
    
    # Try to load existing opportunity
    opp = queue.get_opportunity(task_id)
    if not opp:
        dedupe_hash = hashlib.sha256(task_id.encode()).hexdigest()[:16]
        opp = Opportunity(
            opportunity_id=task_id,
            source="ROUTER_DISPATCH",
            project="WINDOWS_AI_OS",
            description=description,
            objective_id="OBJ-FOUNDATION-1",
            priority=7,
            risk="SAFE",
            estimated_cost=0.0,
            heavy_job=False,
            status="READY",
            target_agent=None,  # Let router decide
            required_capabilities=["WINDOWS_EXECUTION"],
            allowed_scope=["C:\\\\Dev\\\\Windows-AI-OS"],
            allowed_actions=["READ"],
            dedupe_hash=dedupe_hash,
        )
        queue.add_opportunity(opp)
        print(f"[STEP 2] Opportunity injected: {task_id}")
    else:
        print(f"[STEP 2] Opportunity loaded: {task_id}")
        
    scope_str = opp.allowed_scope[0] if opp.allowed_scope else "C:\\\\Dev\\\\Windows-AI-OS"
"""

# Replace the block from `dedupe_hash = ...` to `print(f"[STEP 2]...`
pattern = r"    dedupe_hash = hashlib\.sha256.*?print\(f\"\[STEP 2\] Opportunity injected: \{task_id\}\"\)"
code = re.sub(pattern, replacement.strip(), code, flags=re.DOTALL)

# Now we need to fix scope_str usages.
code = code.replace('scope_str = "C:\\Dev\\Windows-AI-OS"', '')
code = code.replace('"project_path": "C:\\Dev\\Windows-AI-OS",', f'"project_path": scope_str,')
code = code.replace('"scope": ["C:\\Dev\\Windows-AI-OS"],', f'"scope": opp.allowed_scope,')
code = code.replace('"allowed_scope": ["C:\\Dev\\Windows-AI-OS"],', f'"allowed_scope": opp.allowed_scope,')

p.write_text(code)
print("router_dispatch_codex.py patched.")
