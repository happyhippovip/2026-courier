import sys
from scripts.courier_real_worker_adapters import create_real_gemini_adapter

gemini = create_real_gemini_adapter(".")
res = gemini({
    "task_hash": "test-123",
    "worker_id": "GEMINI",
    "target_agent": "GEMINI",
    "payload": {
        "action": "evaluate_goal_completion",
        "prompt": "The immediate opportunity queue is empty. Is the overall goal fully demonstrably complete? Goal: Create a python script 'verify_mac.py' to verify the Mac local repository structure, and independently execute a Windows health check natively. If not complete, identify the next safe concrete dependency/task and output it."
    }
})
print(res)
