import sys
content = open("tests/test_trust_boundary.py").read()
content = content.replace(
'''assert "evidence produced by the acceptance decision path itself" in str(exc.value)''',
'''assert "caller-created or self-certifying MACHINE_ARTIFACT evidence rejected" in str(exc.value)''')
open("tests/test_trust_boundary.py", "w").write(content)
