import re
with open("scripts/courier_safety_dispatcher.py", "r") as f:
    content = f.read()

replacement = """
        for mission in all_missions:
            m_status = mission.get("status")
            if m_status in ("PENDING", "VERIFIED", "FAILED", "BLOCKED", "HUMAN_GATE", "DEDUPED"):
                continue # TERMINAL_CLEANUP already handled effectively by satisfaction engine
"""

new_content = re.sub(
    r"        for mission in all_missions:\n\s*m_status = mission\.get\(\"status\"\)\n\s*if m_status in \(\"VERIFIED\", \"FAILED\", \"BLOCKED\", \"HUMAN_GATE\", \"DEDUPED\"\):\n\s*continue",
    replacement.strip("\n"),
    content,
    flags=re.DOTALL
)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(new_content)
