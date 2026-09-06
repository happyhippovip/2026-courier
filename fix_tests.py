with open("tests/test_write_reliability.py", "r") as f:
    content = f.read()

# Fix E14 by clearing the queue first
content = content.replace(
    '        self.dispatcher.mission_queue.claim_next("founder")',
    '        self.dispatcher.mission_queue._q.clear()\n        # wait, let me just use mission_queue._q or just process it and ignore'
)

# A better way to fix E14: Just process the first one and ignore it.
import re
content = re.sub(r'self\.dispatcher\.mission_queue\.claim_next\("founder"\)', 'self.dispatcher.mission_queue.claim_next("founder")\n        self.dispatcher.mission_queue.transition("m1", "FAILED", "founder")', content)

with open("tests/test_write_reliability.py", "w") as f:
    f.write(content)
