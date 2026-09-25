with open("app/cannon.js", "r") as f:
    js = f.read()

old_line = "const rt=data.live?data.live.text:s.last_result?JSON.stringify(s.last_result,null,2):'Noch kein bestätigtes Ergebnis.';if($('result').textContent!==rt)$('result').textContent=rt;"
new_line = "if(data.live){const rt=data.live.text;if($('result').textContent!==rt)$('result').textContent=rt;}else{$('result').textContent=s.last_result?JSON.stringify(s.last_result,null,2):'Noch kein bestätigtes Ergebnis.';}"
js = js.replace(old_line, new_line)

with open("app/cannon.js", "w") as f:
    f.write(js)
