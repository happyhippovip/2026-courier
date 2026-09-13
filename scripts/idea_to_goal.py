import json
import uuid
from typing import Dict, Any, List
from scripts.idea_inbox import IdeaInbox
from scripts.courier_founder_mode import MultiChatGoalIntake

class IdeaToGoalBridge:
    def __init__(self, inbox: IdeaInbox, intake: MultiChatGoalIntake):
        self.inbox = inbox
        self.intake = intake

    def process_pending_ideas(self) -> List[Dict[str, Any]]:
        processed = []
        pending = self.inbox.get_pending_ideas()
        
        for idea in pending:
            # Phase 2: IDEA -> GOAL -> PLAN mapping
            # For now, simple normalization:
            goal_text = idea["raw_text"].strip()
            if not goal_text:
                self.inbox.update_idea(idea["idea_id"], {"status": "INVALID"})
                continue
                
            # Create the goal via Intake
            goal_id = self.intake.submit_goal(
                source=f"idea_inbox_{idea['idea_id']}",
                goal=goal_text,
                priority=1 if idea.get("priority") == "high" else 5
            )
            
            # Update the idea with provenance
            updated = self.inbox.update_idea(idea["idea_id"], {
                "status": "GOAL_CREATED",
                "goal_id": goal_id,
                "normalized_intent": goal_text
            })
            if updated:
                processed.append(updated)
                
        return processed

if __name__ == "__main__":
    inbox = IdeaInbox()
    intake = MultiChatGoalIntake(workspace_dir=".")
    bridge = IdeaToGoalBridge(inbox, intake)
    processed = bridge.process_pending_ideas()
    print(f"Processed {len(processed)} ideas into goals.")
