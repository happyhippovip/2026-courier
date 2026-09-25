with open("tests/test_server_integration_contract.py", "r") as f:
    text = f.read()

text = text.replace("assert accepted.status_code == 200", "print('BODY:', accepted.get_data(as_text=True)); assert accepted.status_code == 200")
with open("tests/test_server_integration_contract.py", "w") as f:
    f.write(text)
