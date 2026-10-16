# G0 DoD — Ergebnis

Branch `work/g0-dod` ab `integration/v1` @ `7cbbffcbb18fe2e071795a8624f2463c0f715333`.  
Owner: Courier Grok. Kosten 0 EUR. Kein Deploy, kein Merge, kein Force-Push.  
Nicht geändert: `spider_slice.py`, `.github`, `server/app.py`, Ralph. Im Produktcode wird keine Datei gelöscht.

Status: **TEST PASSED**. Nicht `VERIFIED`.

## Roter Lauf

Zuerst nur `tests/test_g0_protect.py`, ohne Modul:

```
python3 -m pytest -q tests/test_g0_protect.py --tb=line
```

```
E   ModuleNotFoundError: No module named 'courier_core.g0_protect'
ERROR tests/test_g0_protect.py
1 error in 0.09s
```

Damit waren Manifest, Hash-Abweichung, fehlende Datei, `UNKNOWN` ungleich `PASS` und Dry-Run ohne Sammelfreigabe rot.

## Grüner Lauf

Nach `courier_core/g0_protect.py`:

```
python3 -m pytest -q tests/test_g0_protect.py --tb=short
```

```
..............                                                           [100%]
14 passed in 0.07s
```

Exit 0. Der eine Test, der eine fehlende Datei verlangt, entfernt nur seine eigene Datei unter `tmp_path`. `deletion_plan` ruft kein Löschen auf; freigegebene und nicht freigegebene Kandidaten bleiben liegen.

Definition: `docs/gates/G0_DOD.md`.
