#!/usr/bin/env python3

def route_task(task_requirements):
    """
    Implements cost-safe routing for main workers and hosted fallbacks.
    Order:
    1. Deterministic local (if resource-safe)
    2. Deterministic hosted/GitHub
    3. Cheap AI
    4. Expensive AI
    """
    print("Evaluating task routing...")
    
    # Simple logic
    if task_requirements.get('can_run_local', True):
        return "LOCAL_WINDOWS"
    elif task_requirements.get('needs_hosted', False):
        return "GITHUB_HOSTED"
    elif task_requirements.get('complexity') == 'high':
        return "EXPENSIVE_AI_PROVIDER"
    else:
        return "CHEAP_AI_PROVIDER"

if __name__ == "__main__":
    assigned = route_task({"can_run_local": True})
    print(f"Task assigned to: {assigned}")
