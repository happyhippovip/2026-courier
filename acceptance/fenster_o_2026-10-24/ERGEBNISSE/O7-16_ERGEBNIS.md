# O7-16 · W14 · Ergebnis ohne Empfänger-ACK gilt als zugestellt · Claude Opus (FENSTER 7)

| Feld | Wert |
|---|---|
| Basis | `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a` |
| PRs gelesen | #845 (`d4824a67b`, offen, nicht gemergt) über GitHub, nur lesend; #846 aus V43/V44 bekannt (F-C1 Kosten, **kein ACK-Bezug**) |
| Testdatei | `O7-16_test_result_without_ack_not_delivered.py` · sha256 `5c8f1e45168d983f17ebc997db76536bc22616053f1dc39943a2524631dbca47` |
| Marker | 3 × `xfail(strict=True, raises=AssertionError)` + 3 Schutztests |
| Lauf auf Basis | `3 passed, 3 xfailed`, Exit 0; mit `--runxfail`: `assert 'DELIVERED' != 'DELIVERED'` |
| Kosten | 0 €; `urlopen` ersetzt, kein Netz; W14-Patch **nicht** angewendet (Patch `de6f7aa5…` liegt nicht in der Cloud) |

## Befund (VERIFIED)
- Der Server bestätigt `POST /tasks/result` mit 200 `{"status":"ACK_RESULT_RECEIVED"}` bzw. `ACK_DUPLICATE` (`server/app.py:514-577`, nur gelesen; `docs/SVSD_COURIER_E2E.md:107`).
- **Echter Defekt (P1, Ergebnis geht verloren):** `scripts/windows_worker/daemon.py:202-224` (`http_post_result`) meldet bei **jeder** 2xx-Antwort `DELIVERED` und liest den Body nie. Danach löscht die Hauptschleife die einzige lokale Kopie (`daemon.py:771-774`, `state_file.unlink()`). Wenn auf dem Port etwas anderes antwortet (Captive Portal, Proxy, fremder Dienst, leere 200), ist das Ergebnis weg, und der Worker hält es für zugestellt.
- **Abgrenzung zu #845:** #845 pinnt die Absturzpfade **nach** einem echten ACK (`ACK_RESULT_RECEIVED`/`ACK_DUPLICATE`, Neustart sendet erneut). Den Fall „2xx ohne ACK“ deckt #845 nicht ab. Er ist hier neu.
- **Bewusst nicht als Befund gewertet:** Der Docstring `daemon.py:205-206` nennt „200 IGNORED means already processed“. Weil der Worker das ausdrücklich als zugestellt behandelt, steht `IGNORED` nicht in den xfail-Fällen; der Server sendet es in dieser Route nicht. Hier entscheidet der Owner.
- Schutz vorhanden (passed): ACK_RESULT_RECEIVED und ACK_DUPLICATE führen zu DELIVERED, 409 führt zu REJECTED.

## Erwartung nach dem Fix
DELIVERED gibt es nur, wenn der JSON-Body `status ∈ {ACK_RESULT_RECEIVED, ACK_DUPLICATE}` enthält. Sonst UNDELIVERED; die lokale Kopie bleibt erhalten und wird erneut zugestellt.
sha256: d2db36953eaa6fe4edd6058f2ae91c7d058e2ebf41e9b4095e48252d0881a4c6
