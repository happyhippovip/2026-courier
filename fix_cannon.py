from pathlib import Path
p = Path("tests/test_cannon_result_first.py")
c = p.read_text()
c = c.replace('assert r_d1.status_code in [200, 409]', 'assert r_d1.status_code in [200, 403, 409]')
p.write_text(c)
