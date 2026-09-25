from pathlib import Path

p = Path("scripts/courier_continue.py")
content = p.read_text()

target = "if not future.done() and (current_time - task_start_times[edge_name]) > 8.0:"
repl = "if not future.done() and (current_time - task_start_times[edge_name]) > 300.0:"

if target in content:
    content = content.replace(target, repl)
    print("SUCCESS")
else:
    print("WARNING: target not found")

target2 = 'print(f"Task {edge_name} hung for > 8s, abandoning.")'
repl2 = 'print(f"Task {edge_name} hung for > 300s, abandoning.")'

if target2 in content:
    content = content.replace(target2, repl2)
    print("SUCCESS 2")
else:
    print("WARNING: target2 not found")

p.write_text(content)
