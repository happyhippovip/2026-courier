import sqlite3
import time
import uuid
import sys
from pathlib import Path
import json

scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

def run_discovery_pass(conn):
    try:
        from scripts.idea_inbox import IdeaInbox
        from scripts.courier_founder_mode import MultiChatGoalIntake
        from scripts.idea_to_goal import IdeaToGoalBridge
        
        inbox = IdeaInbox()
        intake = MultiChatGoalIntake(workspace_dir=str(scripts_dir.parent))
        bridge = IdeaToGoalBridge(inbox, intake)
        
        processed = bridge.process_pending_ideas()
        if processed:
            print(f"[DiscoveryBridge] Processed {len(processed)} ideas into goals.")
            
    except Exception as e:
        import traceback
        print(f"[DiscoveryBridge] Error running real discovery: {e}\n{traceback.format_exc()}")
