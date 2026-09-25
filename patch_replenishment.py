with open("tests/test_auto_replenishment.py", "r") as f:
    text = f.read()
text = text.replace('after polling" "', 'after polling"')
with open("tests/test_auto_replenishment.py", "w") as f:
    f.write(text)
