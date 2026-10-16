with open("courier_worker/service.py", "r") as f:
    content = f.read()

content = content.replace(
    "self._watchers: dict = {}",
    "self._watchers: dict = {}\n        self._cooldown_until = 0.0\n        self._last_resource_state = \"NORMAL\""
)

with open("courier_worker/service.py", "w") as f:
    f.write(content)
