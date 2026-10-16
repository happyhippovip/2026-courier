import re

with open("scripts/coordination_ledger.py", "r") as f:
    text = f.read()

text = text.replace("self.processed_event_ids = set()\\n", "")
text = text.replace("if event.event_id in self.processed_event_ids:\\n", "")
text = text.replace("return\\n", "")
text = text.replace("self.processed_event_ids.add(event.event_id)\\n", "")

text = text.replace(
    "self.missions: Dict[str, Dict] = {}",
    "self.missions: Dict[str, Dict] = {}\n        self.processed_event_ids = set()"
)

text = text.replace(
    "def apply(self, event: CoordinationEvent):\n        self.events.append(event)",
    "def apply(self, event: CoordinationEvent):\n        if event.event_id in self.processed_event_ids:\n            return\n        self.processed_event_ids.add(event.event_id)\n        self.events.append(event)"
)

with open("scripts/coordination_ledger.py", "w") as f:
    f.write(text)
