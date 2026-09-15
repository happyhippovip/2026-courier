import os
import subprocess
from pathlib import Path
from courier_admission_control import TaskPacket
from courier_router import WorkerTarget

class PosixRalphDispatcher:
    def __init__(self, ralph_script_path: str = "scripts/ralph-loop.sh"):
        self.ralph_script_path = ralph_script_path
        
    def dispatch(self, packet: TaskPacket, target: WorkerTarget, workspace_dir: str):
        # 1. Setup .ralph config
        ralph_dir = Path(workspace_dir) / ".ralph"
        ralph_dir.mkdir(exist_ok=True)
        env_file = ralph_dir / ".env"
        
        # Configure tool and model based on capabilities
        tool = "codex"
        if "gemini" in target.capabilities:
            tool = "gemini"
        elif "claude" in target.capabilities:
            tool = "claude"
            
        env_content = f"""RALPH_TOOL="{tool}"
RALPH_MODEL_CAPABILITY="high"
RALPH_THINKING="true"
RALPH_SWITCH_ON_EXHAUSTION="true"
"""
        env_file.write_text(env_content)
        
        # 2. Write prompt
        prompt_file = Path(workspace_dir) / f"task_{packet.task_id}_prompt.md"
        prompt_content = f"""# Goal: {packet.goal_id}
## Task: {packet.task_id}
Contract: {packet.result_contract}
Dependencies: {packet.dependencies}
Authoritative Context: {packet.authoritative_context_refs}

Please implement the required changes.
"""
        prompt_file.write_text(prompt_content)
        
        # 3. Dispatch via ralph-loop.sh wrapper
        max_iterations = 3  # Bounded worker session
        cmd = [
            "bash",
            self.ralph_script_path,
            str(max_iterations),
            str(prompt_file.absolute())
        ]
        
        # Use subprocess to start the worker session
        # This encapsulates the BOUNDED/FRESH WORKER SESSION
        return subprocess.Popen(
            cmd,
            cwd=workspace_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
