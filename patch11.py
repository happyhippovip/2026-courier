with open("tests/test_courier_complete_lifecycle.py", "r") as f:
    content = f.read()

content = content.replace('self.assertEqual(goals[0]["status"], "SATISFIED")', '''print("\\nMISSIONS:")
        import pprint
        pprint.pprint(runtime.queue.read_all())
        print("GOALS:")
        pprint.pprint(goals)
        self.assertEqual(goals[0]["status"], "SATISFIED")''')

with open("tests/test_courier_complete_lifecycle.py", "w") as f:
    f.write(content)
