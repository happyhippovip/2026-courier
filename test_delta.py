import json
tid = "123"
blk = lambda st="ERLEDIGT", i=None, err="-": "COURIER-ERGEBNIS\nAufgabe: %s\nStatus: %s\nGeändert: x\nBeleg: ok\nFehler: %s\nENDE-COURIER" % (i or tid, st, err)
for ch in blk().splitlines(True): print(json.dumps({"delta": ch}), flush=True)
