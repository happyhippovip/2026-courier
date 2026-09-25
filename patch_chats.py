import re
from pathlib import Path

p = Path("server/app.py")
content = p.read_text()

chat_endpoint = """
# ==========================================
# P5 Package 4: Chats
# ==========================================
@app.route("/goals/<goal_id>/chat", methods=["GET", "POST"])
@serialize_state_mutation
def goal_chat(goal_id):
    state = load_state()
    if goal_id not in state.get("goals", {}):
        return jsonify({"error": "Goal not found"}), 404
        
    goal = state["goals"][goal_id]
    chat_history = goal.setdefault("chat_history", [])
    
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        msg = data.get("message")
        sender = data.get("sender", "unknown")
        if not msg:
            return jsonify({"error": "message is required"}), 400
            
        # P5 Rule: limit of 100 messages per goal
        if len(chat_history) >= 100:
            return jsonify({"error": "Chat history full (limit 100 messages)"}), 400
            
        chat_message = {
            "timestamp": __import__("time").time(),
            "sender": sender,
            "message": msg
        }
        chat_history.append(chat_message)
        return jsonify({"status": "POSTED", "message": chat_message})
        
    else:
        # GET
        return jsonify({"chat_history": chat_history})

"""

content = content.replace('if __name__ == "__main__":', chat_endpoint + '\nif __name__ == "__main__":')
p.write_text(content)
print("SUCCESS")
