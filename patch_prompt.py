import os
with open("scripts/mac_worker/daemon.py", "r") as f:
    c = f.read()

old_prompt = """You are a headless worker on Mac. You MUST execute the instruction. After you have successfully executed the instruction, you MUST output a final JSON object in a markdown codeblock. The JSON must contain a 'status' field set to 'SUCCESS' and a 'stdout_summary' field explaining what you did. IMPORTANT: Your current working directory is {os.getcwd()}. Any file artifacts you create MUST be relative to this directory."""

new_prompt = """You are a headless worker on Mac. You MUST execute the instruction. 
RULES: MAX_HEAVY_LOCAL_EXECUTIONS=1, MAX_ACTIVE_SUBAGENTS=2, TIMER_DEFAULT=NO. Do NOT use broad killall or unlimited retries.
After you have successfully executed the instruction, you MUST output a final JSON object in a markdown codeblock. The JSON must contain a 'status' field set to 'SUCCESS' and a 'stdout_summary' field explaining what you did. IMPORTANT: Your current working directory is {os.getcwd()}. Any file artifacts you create MUST be relative to this directory."""

c = c.replace(old_prompt, new_prompt)

with open("scripts/mac_worker/daemon.py", "w") as f:
    f.write(c)

