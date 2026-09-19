with open("tests/test_provider_wait_isolation.py", "r") as f:
    code = f.read()

code = code.replace(
'''def client():
    app.config["TESTING"] = True''',
'''def client(monkeypatch):
    monkeypatch.setattr("server.app.API_KEY", "test-key-12345")
    monkeypatch.setattr("server.app.VERIFIER_API_KEY", "test-key-12345")
    app.config["TESTING"] = True'''
)

with open("tests/test_provider_wait_isolation.py", "w") as f:
    f.write(code)
