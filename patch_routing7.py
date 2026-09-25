import re
with open("tests/test_routing_acceptance_v1.py", "r") as f:
    content = f.read()

replacement = """    if verified.status_code != 200:
        print("VERIFY ERROR:", verified.get_data(as_text=True))
    assert verified.status_code == 200"""
    
content = content.replace("    assert verified.status_code == 200", replacement)

with open("tests/test_routing_acceptance_v1.py", "w") as f:
    f.write(content)
