# W-RECEIPT

Owner: Courier Grok. `BUILD_IF_AUTHORIZED = JA`. Kosten 0 EUR. Kein Deploy, kein Merge, kein Force-Push. `server/app.py`, Ralph und `.github` sind unverändert. Nichts gelöscht.

`VERIFIED` wird nicht behauptet. Ein Receipt mit `RESULT_ACCEPTED` ist die Prüfung dieses Werkzeugs gegen einen Checkout, nicht die Katalogklasse VERIFIED.

Basis: `integration/v1` @ `7cbbffcbb18fe2e071795a8624f2463c0f715333`.  
PR #602 ist dort nicht enthalten. `source_sha` folgt trotzdem derselben Regel wie dort: genau 40 kleine Hex-Zeichen und gleich `git rev-parse HEAD`.

## Werkzeug

- Modul: `courier_core/verifier_receipt.py`
- CLI: `scripts/verifier_receipt.py`
- Tests: `tests/test_verifier_receipt.py`

Pflichtfelder: `result` (`RESULT_ACCEPTED` oder `RESULT_REJECTED`), `pr_head_sha`, `source_sha`, `artifacts[].sha256`, `test_command`, `exit_code`, `skipped`, `timestamp`, `host`, `platform`.

`issue` setzt `RESULT_ACCEPTED` nur bei Exit 0, `skipped == 0`, sauberem Blob und vorhandenem Checkout-SHA. `verify` akzeptiert nur denselben Fall. Ein späterer Commit, der das Receipt nur ablegt, ist ein anderer SHA. Dafür gibt es `verify --revision <bezeugter SHA>`. Der Default vergleicht mit `HEAD` und lehnt die Abweichung ab.

## Rote Tests, dann Implementierung

Vor dem Modul, zweimal:

```
python3 -m pytest -q tests/test_verifier_receipt.py --tb=line
```

```
E   ModuleNotFoundError: No module named 'courier_core.verifier_receipt'
ERROR tests/test_verifier_receipt.py
1 error in 0.10s
```

Die Ablehnungsfälle waren damit rot, weil keiner laufen konnte: SHA-Abweichung, Artefakt-Hash, Exit ungleich 0, fehlendes Feld, Skip als Erfolg, unbekannter Zustand (`VERIFIED`), Skip-Token, Plattform, späterer HEAD.

Nach der Implementierung:

```
python3 -m pytest -q tests/test_verifier_receipt.py
```

```
..............                                                           [100%]
14 passed in 0.48s
```

Exit 0, keine Skips. Dieselbe Ausgabe lieferte `issue --run`.

## Beispiel-Receipt

Bezeugter Commit: `77dcb5496d7ebcb815b1a265eec41ae86b1e4ccf`  
Datei: `docs/work/verifier_receipt.json`  
Kommando: `python3 -m pytest -q tests/test_verifier_receipt.py`  
Host `cursor`, Plattform `linux`, Zeitstempel `2026-10-13T15:22:15.872989+00:00`.

Am bezeugten Commit:

```
python3 scripts/verifier_receipt.py verify docs/work/verifier_receipt.json --repo .
{"result": "RESULT_ACCEPTED", "reason": ""}
```

Exit 0. `pr_head_sha` und `source_sha` sind beide `77dcb5496d7ebcb815b1a265eec41ae86b1e4ccf`.

Ein Commit kann seinen eigenen SHA nicht enthalten. Gemessen an `80b02dd87a76731ad4d08a1657cc71d47194422a`, dem Commit, der das JSON erstmals ablegt:

```
python3 scripts/verifier_receipt.py verify docs/work/verifier_receipt.json --repo .
{"result": "RESULT_REJECTED", "reason": "sha_mismatch"}
```

Exit 1.

```
python3 scripts/verifier_receipt.py verify docs/work/verifier_receipt.json --repo . --revision 77dcb5496d7ebcb815b1a265eec41ae86b1e4ccf
{"result": "RESULT_ACCEPTED", "reason": ""}
```

Exit 0. Der Default lehnt den neueren Checkout ab. `--revision` prüft die Blobs von `77dcb5496`. Das ist kein Beleg für einen späteren PR-Head. Der PR-Text enthält das Receipt, das nach dem letzten Commit gegen genau diesen Head erzeugt und geprüft wurde.

## Ablehnung am echten Receipt

Jede Zeile ist `scripts/verifier_receipt.py verify` gegen eine Kopie von `docs/work/verifier_receipt.json`, Exit 1:

```
sha_mismatch       {"result": "RESULT_REJECTED", "reason": "sha_mismatch"}
artifact_hash      {"result": "RESULT_REJECTED", "reason": "artifact_hash"}
exit_nonzero       {"result": "RESULT_REJECTED", "reason": "exit_nonzero"}
missing_field      {"result": "RESULT_REJECTED", "reason": "missing_field"}
skip_as_success    {"result": "RESULT_REJECTED", "reason": "skip_as_success"}
unknown_state      {"result": "RESULT_REJECTED", "reason": "unknown_state"}
SKIPPED token      {"result": "RESULT_REJECTED", "reason": "skip_as_success"}
```

`result: VERIFIED` ist ein unbekannter Zustand und wird nicht akzeptiert.
