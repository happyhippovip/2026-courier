with open("tests/test_courier_complete_lifecycle.py", "r") as f:
    content = f.read()

content = content.replace('def _run(self, goal: str):', '''def _run(self, goal: str):
        import logging
        logging.basicConfig(level=logging.DEBUG)''')

with open("tests/test_courier_complete_lifecycle.py", "w") as f:
    f.write(content)
