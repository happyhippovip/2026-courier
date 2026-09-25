with open("app/cannon.js", "r") as f:
    js = f.read()

# Replace result handling
old_line = "$('result').textContent=s.last_result?JSON.stringify(s.last_result,null,2):'Noch kein bestätigtes Ergebnis.';"
new_line = "$('result').textContent=data.live?data.live.text:s.last_result?JSON.stringify(s.last_result,null,2):'Noch kein bestätigtes Ergebnis.';"
js = js.replace(old_line, new_line)

with open("app/cannon.js", "w") as f:
    f.write(js)
