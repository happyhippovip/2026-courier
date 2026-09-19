with open("/Users/user/.gemini/antigravity/brain/c61b931a-e4f1-476d-b9d2-431218079df5/.system_generated/tasks/task-97042.log") as f:
    import re
    m = re.search(r"where 'MOCK_LEDGER IN ENV: (.*?)' = CompletedProcess", f.read(), re.DOTALL)
    if m:
        s = m.group(1).replace("\\n", "\n")
        print(s)
