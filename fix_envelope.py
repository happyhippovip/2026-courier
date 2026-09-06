with open("scripts/courier_safety_dispatcher.py", "r") as f:
    content = f.read()

content = content.replace(
    'requested_model: Optional[str] = None',
    'requested_model: Optional[str] = None\n    native_attempt: int = 1'
)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(content)
