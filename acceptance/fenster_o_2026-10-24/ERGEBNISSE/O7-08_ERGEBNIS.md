# O7-08 · B4 · Bytes A ≠ Bytes C trotzdem PASS · Claude Opus (FENSTER 7)

| Feld | Wert |
|---|---|
| Basis | `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a` |
| Testdatei | `O7-08_test_bytes_changed_after_post.py` · sha256 `a138c38e80762d73b633275c4f56641b56b271ee487aa1ccfb5aed2f51e6c2a7` |
| Marker | `xfail(strict=True, raises=AssertionError)` |
| Lauf auf Basis | `1 xfailed in 2.24s`, Exit 0; mit `--runxfail`: FINAL für B vorhanden (`final-86049477fc6ef0f2`, `inputs_digest=8991…` = alter Hash) |
| Umfang | echter V1-Controller und synthetischer Worker (Golden-Harness), ein lokaler Heavy-Job, 0 €, keine Prozesse übrig |

## Befund (VERIFIED)
- **Schutz vorhanden, nicht gefunden:** Werden die Bytes **vor** dem Post von B verändert, wird B blockiert (`input_digest_mismatch`). Belegt durch `tests/test_ledger_chain_abcd_restart.py:128` (Katalog-Input, A→B→C→D) und `tests/test_ledger_bridge_verified_inputs.py:173-187`.
- **Echter Defekt (P2, TOCTOU):** Die Bridge prüft den Digest **einmal**, beim Post (`scripts/ledger_v1_bridge.py:282-290` → `_resolve_inputs` `:498-499`). `_feedback` (`:121-240`) prüft die Eingaben vor FINAL **nicht erneut**. Kein Adapter liest `params.inputs`; im Code erwähnt nur der Docstring `adapters/provider_exec.py:16` „inputs“. Ändern sich die Bytes von A nach dem Post von B, läuft B trotzdem durch und bekommt FINAL. Dessen Evidence nennt den **alten** `inputs_digest`, auf der Platte liegen aber andere Bytes. Für die Kette A→B→C heißt das: C erbt eine Kette, deren erster Hash nicht mehr den Bytes entspricht.
- Einschränkung: Der synthetische B-Adapter liest die Eingabebytes gar nicht. Belegt ist also „FINAL über veränderte Eingaben“, nicht „B hat falsche Bytes verarbeitet“.

## Erwartung nach dem Fix
Vor FINAL (oder beim Start durch den Worker) wird jedes `params.inputs[i]` gegen `_file_sha256` geprüft. Bei Abweichung gibt es kein FINAL, sondern BLOCKED `input_digest_mismatch`.
sha256: 169f96bcdb2708a0a4208dffdcc2ee0690dd4330297b3562dad6d3142c432b5f
