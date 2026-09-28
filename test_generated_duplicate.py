import uuid
import server.app

def mock_formulate(self, text, idea_type):
    # Returns duplicate task IDs
    return "wf1", [{"task_id": "duplicate-1"}, {"task_id": "duplicate-1"}]

server.app.ChiefCommander.formulate_workflow_plan = mock_formulate
# we need to initialize app or just inspect the code
