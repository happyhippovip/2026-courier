from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class HandoffContext:
    workkey: str
    reason: str
    required_action: str
    context_data: Dict[str, Any]

class HumanHandoffContract:
    """MAC-09: Generate minimal actionable NEEDS YOU handoffs."""
    @staticmethod
    def generate_handoff(context: HandoffContext) -> Dict[str, Any]:
        return {
            "status": "NEEDS_YOU",
            "workkey": context.workkey,
            "reason": context.reason,
            "action_required": context.required_action,
            "context": context.context_data,
            "machine_readable_instruction": f"Provide {context.required_action} to proceed."
        }
