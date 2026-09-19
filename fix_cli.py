import re

p = 'app/cannon/cli.py'
with open(p, 'r') as f:
    cli = f.read()

new_build = """def build_identity():
    files = sorted((ROOT / 'app/cannon').glob('*.py')) + [ROOT / name for name in
             ['app/server.py', 'app/cannon.html', 'app/cannon.js', 'app/cannon.css']]
    return digest({str(p.relative_to(ROOT)): file_hash(p) for p in files if p.exists()})
"""

cli = re.sub(r'def build_identity\(\):.*?return digest\(\{.*?\}\)\n', new_build, cli, flags=re.DOTALL)

with open(p, 'w') as f:
    f.write(cli)
