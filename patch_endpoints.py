import re
from pathlib import Path

p = Path("server/app.py")
content = p.read_text()

new_endpoints = """
# ==========================================
# P5 Package 1 & 2: Profiles and Groups
# ==========================================
@app.route("/profiles", methods=["GET"])
def list_profiles():
    state = load_state()
    profiles = {}
    for wid, w in state.get("workers", {}).items():
        profiles[wid] = {
            "id": wid,
            "type": "worker",
            "capabilities": w.get("capabilities", []),
            "groups": w.get("groups", []),
            "community_id": w.get("community_id", "public"),
            "tasks_completed": w.get("tasks_completed", 0),
            "custom_profile": state.get("profiles", {}).get(wid, {})
        }
    for uid, up in state.get("profiles", {}).items():
        if uid not in profiles:
            profiles[uid] = {
                "id": uid,
                "type": "user",
                "custom_profile": up
            }
    return jsonify({"profiles": list(profiles.values())})

@app.route("/users/<id>", methods=["GET", "POST"])
@serialize_state_mutation
def user_profile(id):
    state = load_state()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        # In this sandbox implementation, we allow anyone with API_KEY to write profiles
        # (simulating owner or system orchestrator)
        token = request.headers.get("Authorization", "")
        if token != f"Bearer {API_KEY}" and API_KEY not in INSECURE_API_KEYS:
            return jsonify({"error": "Unauthorized"}), 401
            
        profiles_dict = state.setdefault("profiles", {})
        profiles_dict[id] = data.get("custom_profile", profiles_dict.get(id, {}))
        return jsonify({"status": "UPDATED", "profile": profiles_dict[id]})
    else:
        # GET
        w = state.get("workers", {}).get(id)
        if w:
            prof = {
                "id": id,
                "type": "worker",
                "capabilities": w.get("capabilities", []),
                "groups": w.get("groups", []),
                "community_id": w.get("community_id", "public"),
                "tasks_completed": w.get("tasks_completed", 0),
                "custom_profile": state.get("profiles", {}).get(id, {})
            }
        else:
            up = state.get("profiles", {}).get(id)
            if up:
                prof = {"id": id, "type": "user", "custom_profile": up}
            else:
                return jsonify({"error": "Profile not found"}), 404
        return jsonify(prof)

@app.route("/groups", methods=["GET"])
def list_groups():
    state = load_state()
    groups_tally = {}
    for wid, w in state.get("workers", {}).items():
        for g in w.get("groups", []):
            groups_tally[g] = groups_tally.get(g, 0) + 1
            
    # Include groups that might be empty but are required by active tasks
    for tid, task in state.get("tasks", {}).items():
        for g in task.get("required_groups", []):
            if g not in groups_tally:
                groups_tally[g] = 0
                
    return jsonify({"groups": [{"name": k, "active_workers": v} for k, v in groups_tally.items()]})

"""

content = content.replace('if __name__ == "__main__":', new_endpoints + '\nif __name__ == "__main__":')
p.write_text(content)
print("SUCCESS")
