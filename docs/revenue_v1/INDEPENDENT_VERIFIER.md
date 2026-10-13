# Unabhängiger Verifier Revenue V1 (D5)

Modul: `scripts/revenue_v1_independent_verifier.py`, `VERIFIER_VERSION = "1.0.0"`. Eingehängt über `scripts/revenue_v1_safety_baseline.py` (`verify` und indirekt `reconcile`), das den Verifier als **eigenen Prozess** startet – keine Workflow-Änderung nötig. Der Workflow-Schritt „Execute Independent Verifier“ ruft weiterhin `revenue_v1_safety_baseline.py verify` auf und scheitert (Exit ≠ 0), wenn das Verdict nicht PASS ist.

Standalone: `python3 scripts/revenue_v1_independent_verifier.py task.json work_dir result.json [remote_url]` → JSON-Verdict, Exit 0 nur bei PASS.

## Checkliste Courier-Prüfer
| # | Anforderung | Beleg |
|---|---|---|
| 1 | Eigenes Modul, kein Import aus `revenue_v1_safety_baseline`/Worker | `scripts/revenue_v1_independent_verifier.py:10-19` (nur Stdlib + optional `yaml`); eigene Regeln `:65-161`; Test `tests/test_revenue_v1_independent_verifier.py:148` |
| 2 | Erwartete Befunde aus Roh-Blobs am SHA per `git show SHA:pfad`, nicht aus Arbeitsbaum | Fetch ohne Checkout `:45-49`; `git ls-tree`/`git show` `:52-58`; Ableitung `:164-172`; Test `tests/...independent_verifier.py:69` (kein `.github` im Arbeitsbaum) |
| 3 | Datei-Hashes in report.json gegen git am SHA | `:167` (sha256 der Blobs), Vergleich `:198-199`; Tests `:89`, `:100` |
| 4 | Fail-closed: Abweichung → MISMATCH, fehlende Datei/Exception → FAIL, nie PASS | fehlende Datei `:192-193`; Abweichungen `:210`; Exception `:226`; `accepted` nur bei PASS `:228`; Exit-Code `:238`; Aufrufer fail-closed `scripts/revenue_v1_safety_baseline.py:328-358`; Tests `:112`, `:119`, `:127`, `:132`, `tests/test_revenue_v1_safety_baseline.py` (`test_verify_rejects_mismatch`, `test_run_independent_verifier_fail_closed`) |
| 5 | pytest mit manipuliertem report.json und manipulierter Datei, beide abgelehnt | `tests/test_revenue_v1_independent_verifier.py:77` (Befund entfernt, Hash sogar nachgezogen → MISMATCH), `:89` (Hash in report.json gefälscht → MISMATCH), `:100` (Workflow-Datei vor Analyse verändert → MISMATCH) |
| 6 | Verdict nennt Name, Version, sha256 (analog `courier_core/verification.py:88-94` `verifier_identity`) | `:23-36`, im Verdict `:229`; in `verified.json` als `independent_verifier` (`scripts/revenue_v1_safety_baseline.py:355-356`); Test `:142` |

## Grenzen
- Die Regeln sind bewusst zweimal implementiert (Worker und Verifier). Gleiches Fehlverständnis in beiden Implementierungen würde nicht auffallen; der Verifier prüft Übereinstimmung mit den Roh-Blobs, nicht die fachliche Richtigkeit der Regeln.
- Läuft der Verifier ohne PyYAML, der Worker aber mit, ergibt das MISMATCH (parse_modes) – fail-closed, aber im CI nur mit dem Patch in `WORKFLOW_PATCH.md` zuverlässig PASS. Lokal belegt: System-Python ohne PyYAML → `MISMATCH: parse_modes differ, findings differ (report 14, expected 13)` bei requests.
- Netzwerkzugriff auf github.com im Verifier nötig (eigener Fetch).
