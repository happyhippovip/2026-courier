# 09/50 | WORKER UND VERIFIER GETRENNT PRÜFEN

## Authentifizierungs- und Rollenunterscheidung im bestehenden Vertrag
Der vorhandene Ledger- und Serververtrag verlangt eine strikte kryptografische Trennung von Worker (Ausführender) und Verifier (Prüfer):

1. **Unterschiedliche Identitäten zwingend (Server-Vertrag):** 
   In `server/app.py` prüft der Decorator `@require_verifier_auth` explizit, ob `API_KEY == VERIFIER_API_KEY`. Ist dies der Fall, wird die Serverfunktion verweigert (HTTP 503 "Courier verifier authority is not configured").
2. **Self-Certification Guard (Server-Vertrag):** 
   Die Methode `/tasks/verify` lehnt zudem einen Nachweis direkt mit HTTP 400 ("self-certification prohibited") ab, falls der beim Abschluss des Tasks berechnete `producer_principal` mit dem aktuellen `verifier_principal` übereinstimmt. Diese Hash-Identitäten leiten sich direkt aus den genutzten Bearer-Tokens ab.
3. **Physischer Ledger-Schutz:**
   In `scripts/agent_handoff_ledger.py` wird in `has_physical_proof` und beim Eintragen des Artefakts (`update()`) geprüft, ob `producer_id == verifier_id`. Trifft dies zu (oder ist einer der Akteure gleich demjenigen, der das Ledger-Update auslöst), bricht das System mit einem `SelfCertificationError` ab und verhindert den Übergang zu `CLEAN_IDLE=YES`.

## Korrekturen in synthetischen Testkontexten
In einigen Testsuites wurden fälschlicherweise für beide Rollen dieselben Dummywerte (z.B. `"test-key-12345"`) verwendet, was die Trennung nicht realistisch abbildete. Dies wurde in folgenden Dateien bereinigt, um getrennte Kontexte vorzugeben:
* `tests/test_provider_wait_isolation.py` (angepasst auf `"test-verifier-12345"`)
* `tests/test_result_duplicates.py` (angepasst auf `"test_verifier"`)
* `tests/test_windows_runtime_torture.py` (angepasst auf `"test-verifier-12345"`)

## Echte Verifikationstests (Bereits belegt)
Dass unzulässige Verifikationen sicher abgewiesen werden, wird im Projekt durch spezifische Sicherheitstests nachgewiesen und wurde nicht abgeschwächt:
* `tests/test_server_integration_contract.py::test_verifier_authority_fails_closed_when_shared_with_worker` testet die HTTP 503-Sperre, falls Verifier- und Worker-Schlüssel gleich konfiguriert sind.
* `tests/test_ledger_authenticated_receipts.py::test_forged_metadata_never_counts` manipuliert künstlich `verifier_id = producer_id` (Angriffsvektor: `same_identity`) und beweist, dass das Ledger einen `SelfCertificationError` wirft.
