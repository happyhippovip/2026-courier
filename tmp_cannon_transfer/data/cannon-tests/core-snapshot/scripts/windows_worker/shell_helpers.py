import re
import os
import subprocess

def preprocess_instruction(instruction: str) -> str:
    """
    Translates common unix shell commands into native PowerShell equivalents 
    before execution to prevent CommandNotFoundException.
    """
    if not instruction:
        return instruction
        
    cmd = instruction.strip()
    
    # Simple regex to catch grep at the start
    if re.match(r"^grep\b", cmd):
        cmd = re.sub(r"^grep\b", "Select-String", cmd)
        cmd = cmd.replace(" -r ", " ")
        cmd = cmd.replace(" -R ", " ")
        return cmd
        
    if re.match(r"^which\b", cmd):
        return re.sub(r"^which\b", "Get-Command", cmd)
        
    if re.match(r"^find\b", cmd):
        return re.sub(r"^find\b", "Get-ChildItem -Recurse", cmd)
        
    return cmd
