#!/usr/bin/env python3
import json
import os

def load_entitlements(license_path="license.json"):
    """
    Loads commercial tier limits and capabilities.
    Fails open to a FREE/COMMUNITY tier if missing or invalid.
    """
    default_entitlement = {
        "tier": "COMMUNITY",
        "max_concurrent_tasks": 2,
        "features": ["local_execution", "basic_reporting"]
    }
    
    if os.path.exists(license_path):
        try:
            with open(license_path, 'r') as f:
                data = json.load(f)
                return data.get("entitlements", default_entitlement)
        except Exception:
            pass
            
    return default_entitlement

def check_capability(capability_name):
    entitlements = load_entitlements()
    return capability_name in entitlements.get("features", [])

def get_task_limit():
    entitlements = load_entitlements()
    return entitlements.get("max_concurrent_tasks", 1)

if __name__ == "__main__":
    ents = load_entitlements()
    print(f"Current Tier: {ents['tier']}")
    print(f"Max Concurrent Tasks: {ents['max_concurrent_tasks']}")
    print(f"Features: {ents['features']}")
