# M2 — SKIPPED_TEST_VALIDITY (Muse 2)

Stand: 2026-09-28, Quelle: Repo-Reads (kein Testlauf, keine Revalidierung)

## USER_PROBLEM (Operator-Sicht)
"1 skipped" — versteckt das einen echten Mangel, oder ist das ein ehrlicher
Plattform-Vorbehalt? Und wer testet das Uebersprungene stattdessen?

## CURRENT_RUNTIME_TRUTH (belegt)
- Genau EIN `pytest.skip` im gesamten `tests/`-Baum (dedizierte Suche, 1 Treffer):
  `tests/test_artifact_upload_flow.py:462-466` —
  `test_mac_worker_uploads_and_verifier_reconciles`, skippt auf win32 mit
  "Mac daemon requires fcntl". Alles andere sind `parametrize` (keine Skips).
- Rechenprobe: 14 + 29/30 + 11 + 3 = 57 passed + 1 skipped — passt exakt zu GATE.
- Der Skip-Grund ist ehrlich (Plattform-Faehigkeit fcntl). ABER die Coverage:
  Der Mac-Daemon-E2E-Upload-Pfad laeuft damit auf Windows NIE — und im
  Mac-RUN-Harness wird der Mac-Daemon ebenfalls nicht gestartet (Worker dort ist
  `scripts.integration_contract`, siehe M7). Der Pfad hat derzeit NIRGENDS
  einen Executor.

## VERDIKT
M2-CLOSED mit Fund: Skip VALIDE (ehrlicher Gate, korrekter Grund), aber
Coverage VERWAIST (M2-ORPHAN-1): Mac-E2E-Upload wird auf keiner Plattform
ausgefuehrt. Das ist kein.Fail des Tests, sondern eine Luecke im
Ausfuehrungsplan. Jeder Mac-Upload-Beweis fehlt physisch UND synthetisch.

## ACCEPTANCE_REQUIREMENT
M2.1: Jeder Skip nennt seinen abdeckenden Lauf (`SKIP → COVERED_BY:
<Plattform>/<Run-ID>`) oder steht auf der Orphan-Liste.
M2.2: Die Orphan-Liste ist Teil des Proof-Status (nicht versteckt im Log).

## MISSING_SYSTEM_SUPPORT
- Kein Skip→Coverage-Mapping, kein Mac-pytest-Runner im Plan.
- RUN-Harness startet keinen echten Mac-Daemon (M7).

## PREPARABLE_NOW
- Dieses Paket + Orphan-Liste (1 Eintrag: Mac-E2E-Upload).
- Regel-Entwurf M2.1/M2.2.

## BLOCKED_UNTIL
- Mac-Ausfuehrungsort (Runner ODER reparierter RUN-Harness mit echtem Daemon).

## NEXT
M3 (Zahlen-/Diff-Widersprueche) — M2 liefert: Skip-Seite ist sauber gezaehlt.
