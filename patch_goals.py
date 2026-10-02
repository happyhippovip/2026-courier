with open('tests/test_server_app_uncovered.py', 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace('state["goals"]["g1"] = {"status"', 'state["goals"]["g1"] = {"goal_id": "g1", "status"')
with open('tests/test_server_app_uncovered.py', 'w', encoding='utf-8') as f:
    f.write(text)
