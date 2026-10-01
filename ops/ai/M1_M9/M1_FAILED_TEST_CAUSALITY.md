# M1 — FAILED_TEST_CAUSALITY (Muse 1)

Stand: 2026-09-28, Quelle: Repo-Reads (kein Testlauf, keine Revalidierung)

## USER_PROBLEM (Operator-Sicht)
Sind Tests rot? Falls ja: Warum — echter Assert-Fe Fehler, kaputte Umgebung
oder Sammel-Fehler? "0 failed" allein beantwortet das nicht.

## CURRENT_RUNTIME_TRUTH (belegt)
- Targeted-Suites (GATE: 14+29+11+3 = 57): `test_p3_server_idempotency.py` und
  `test_artifact_upload_flow.py` laden den Server via `tests/p3_preview.py`
  (`load_patched_server`), das Env-Keys per monkeypatch setzt (`:18-22`) VOR
  `exec_module` — sie sind env-unabhaengig. `test_integration_contract.py` und
  `test_result_identity_binding.py` importieren nur `scripts.integration_contract`
  (kein Env noetig). Die "57/1/0"-Meldung ist in sich konsistent.
- Ausserhalb der Boundary: 3 Suiten importieren `server.app` auf Modul-Ebene
  OHNE Env-Vorbereitung und sterben bei Collection mit SystemExit, wenn keine
  Keys exportiert sind (`server/app.py:12-17`): `test_server_integration_contract.py:12`,
  `test_marathon.py:13`, `test_failure_recovery_matrix.py:6-7` (plus Kreuz-Import
  aus erstem, `:6`). `test_duplicates.py:7-11` setzt Env selbst und ist fein.
- `tests/conftest.py` und `conftest.py` existieren NICHT (beide Leseversuche =
  Datei fehlt). Es gibt keinen zentralen Env-/Pfad-Gate.
- Gemeldeter Assert-Fehlschlag (rot im eigentlichen Sinn): keiner. Die einzige
  Failure-Kausalitaet im Repo ist Collection-durch-Env.

## VERDIKT
M1-CLOSED: Innerhalb der Targeted-Boundary gibt es keine Failure-Kausalitaet zu
analysieren (0 failed, Mechanik konsistent). Ausserhalb gibt es genau eine:
`BARE_PYTEST → COLLECTION_ERROR → SystemExit (fehlende Keys)`, Ursache
Fail-closed-Import + fehlendes conftest. Kein Test wurde je "rot durch Assert"
gemeldet — das ist kein Freispruch, nur die Aktenlage.

## MISSING_SYSTEM_SUPPORT
- Kein conftest.py (Env + Pfad), keine Testing-Doku mit Env-Gate.
- Keine Failure-Taxonomie (ASSERT vs COLLECTION vs ENV vs SKIP) in Reports.

## PREPARABLE_NOW
- Dieses Paket + Kausal-Kette oben (reicht als Operator-Antwort auf "warum rot?").
- conftest-Entwurf als Vorschlag (nicht anlegen ohne Owner: Test-Owner entscheidet).

## BLOCKED_UNTIL
- Runner fuer JEDE Ausfuehrung (hier verboten + Shell down) — M1 braucht keinen.

## NEXT
M2 (Skip-Validitaet) — M1 liefert: Skip ist die einzige Nicht-Green-Kategorie.
