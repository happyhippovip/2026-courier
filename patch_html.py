import re

p = 'tmp_cannon_transfer/app/cannon.html'
with open(p, 'r') as f:
    html = f.read()

html = html.replace('<select id="mode"><option>NORMAL</option></select>', '<select id="mode"><option>BEGRENZT</option><option>UNENDLICH</option></select>')
html = html.replace('<select id="count"><option>5</option><option>10</option></select>', '<select id="count"><option>1</option><option>5</option><option>10</option><option>100</option><option>1000</option><option>10000</option><option>100000</option><option>1000000</option></select>')

with open(p, 'w') as f:
    f.write(html)
print("Patched HTML.")
