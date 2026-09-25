with open("app/cannon.js", "r") as f:
    js = f.read()

# Replace result handling again
old_line = "$('result').textContent=data.live?data.live.text:s.last_result?JSON.stringify(s.last_result,null,2):'Noch kein bestätigtes Ergebnis.';"
new_line = "const rt=data.live?data.live.text:s.last_result?JSON.stringify(s.last_result,null,2):'Noch kein bestätigtes Ergebnis.';if($('result').textContent!==rt)$('result').textContent=rt;"
js = js.replace(old_line, new_line)

with open("app/cannon.js", "w") as f:
    f.write(js)
