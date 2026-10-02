import sys

def patch():
    with open('server/app.py', 'r') as f:
        content = f.read()

    # In /goals endpoint:
    # step["task_id"] = f"task-{uuid.uuid4().hex[:8]}"
    content = content.replace(
        'step["task_id"] = f"task-{uuid.uuid4().hex[:8]}"',
        'step.setdefault("task_id", f"task-{uuid.uuid4().hex[:8]}")'
    )
    # Also fix the else branch for the planner
    content = content.replace(
        '"task_id": f"task-{uuid.uuid4().hex[:8]}",',
        '"task_id": step.get("task_id", f"task-{uuid.uuid4().hex[:8]}"),'
    )

    with open('server/app.py', 'w') as f:
        f.write(content)
    print("Patched app.py for task_id")

if __name__ == '__main__':
    patch()
