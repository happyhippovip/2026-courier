import re

with open("scripts/mac_worker_adapter.py", "r") as f:
    content = f.read()

# Replace hardcoded strings with Path objects so they can be mocked
content = content.replace('os.makedirs("results/incoming", exist_ok=True)', 
                          'incoming_dir = Path("results/incoming")\n            incoming_dir.mkdir(parents=True, exist_ok=True)')
content = content.replace('with open(f"results/incoming/{task[\'task_id\']}_result.json", \'w\') as f:', 
                          'with open(incoming_dir / f"{task[\'task_id\']}_result.json", \'w\') as f:')

content = content.replace('incoming = Path(f"results/incoming/{task[\'task_id\']}_result.json")',
                          'incoming_dir = Path("results/incoming")\n    incoming_dir.mkdir(parents=True, exist_ok=True)\n    incoming = incoming_dir / f"{task[\'task_id\']}_result.json"')

# Clean up any leftover os.makedirs since we replaced it with Path.mkdir
content = content.replace('    os.makedirs("results/incoming", exist_ok=True)\n', '')

with open("scripts/mac_worker_adapter.py", "w") as f:
    f.write(content)
