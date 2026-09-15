import sys
path = "scripts/courier_founder_mode.py"
data = open(path).read()

to_find = """                if not mission_result or mission_result.get("status") == "NO_PENDING_MISSION":"""
to_replace = """                if not mission_result or mission_result.get("status") in ("NO_PENDING_MISSION", "DISCOVER_FROM_ACTIVE_ROOT_GOAL_GAPS", "QUIESCENT_WAKEABLE"):"""

if to_find in data:
    data = data.replace(to_find, to_replace)
    open(path, "w").write(data)
    print("PATCH APPLIED")
else:
    print("FAILED")
