# TRUSTED HASH / SERVER BYTES / ARTIFACT AUTHORITY

## Fall A: task-owned expected_sha256 bleibt authoritative
SOURCE= scripts/courier_verifier.py (verify_artifacts liest iterativ expected_art aus task.get("artifacts"))
TEST= tests/test_artifact_upload_flow.py (test_verifier_checks_expected_sha256)
CURRENT_BEHAVIOR= task_expected_sha256 wird ausschließlich aus `task["artifacts"]` ermittelt, nie aus dem Result-Payload.
EXPECTED= PASS
PASS|DEFECT= PASS
EVIDENCE= Code und Tests bestätigen vollständige Authority durch Task.

## Fall B: worker-controlled expected_sha256 kann Authority NICHT überschreiben
SOURCE= scripts/integration_contract.py (discard expected_sha256), scripts/courier_verifier.py (liest es nicht aus worker art)
TEST= tests/test_artifact_upload_flow.py (test_verifier_ignores_worker_controlled_expected_sha256)
CURRENT_BEHAVIOR= `integration_contract.py` entfernt `expected_sha256` aus validierten Worker-Artifacts. `courier_verifier.py` ignoriert worker `expected_sha256` komplett.
EXPECTED= PASS
PASS|DEFECT= PASS
EVIDENCE= Manipulationsversuche des Workers werden durch Schema Check & Verifier Logik ignoriert.

## Fall C: Worker kann durch Weglassen von expected_sha256 keine Erwartung umgehen
SOURCE= scripts/courier_verifier.py ("Check for Case 5 Omission Bypass")
TEST= tests/test_artifact_upload_flow.py (Verhindert Bypass durch Omission)
CURRENT_BEHAVIOR= Wenn `task` ein `expected_sha256` verlangt, der Worker dieses File aber weglässt, fällt der Verifier in der finalen Loop ("Omission Bypass") durch und returniert `FAIL`.
EXPECTED= PASS
PASS|DEFECT= PASS
EVIDENCE= Die Omission-Prüfung sichert ab, dass geforderte Hashes geliefert werden müssen.

## Fall D: wenn Task keine Erwartung besitzt: nur definierter Legacy-Pfad
SOURCE= scripts/courier_verifier.py (verify_uploaded_artifact)
TEST= Vorhandene artifact tests ohne `expected_sha256`.
CURRENT_BEHAVIOR= Wenn `task_expected_sha256` `None` ist, prüft `verify_uploaded_artifact` nur die Upload-Integrität (Size & Blob Hash == Worker Hash).
EXPECTED= PASS
PASS|DEFECT= PASS
EVIDENCE= Legacy-Pfad wird ordnungsgemäß ausgeführt.

## Fall E: korrekte tatsächliche Server-Bytes -> PASS
SOURCE= scripts/courier_verifier.py (hashlib.sha256(data).hexdigest() == task_expected_sha256)
TEST= tests/test_artifact_upload_flow.py (test_verifier_checks_expected_sha256)
CURRENT_BEHAVIOR= Wird bestanden.
EXPECTED= PASS
PASS|DEFECT= PASS
EVIDENCE= Echter Hashvergleich bestätigt die Server-Bytes.

## Fall F: falsche tatsächliche Server-Bytes -> FAIL
SOURCE= scripts/courier_verifier.py
TEST= tests/test_artifact_upload_flow.py (Hash mismatch test cases)
CURRENT_BEHAVIOR= Falsche Bytes resultieren in `FAIL` vom Verifier.
EXPECTED= PASS
PASS|DEFECT= PASS
EVIDENCE= Verifier lehnt ab.

## Fall G: malformed target -> FAIL CLOSED
SOURCE= scripts/courier_verifier.py (known_targets check)
TEST= implizit in Verifier Logik abgedeckt.
CURRENT_BEHAVIOR= `target` das keines der `known_targets` enthält, gibt `FAIL` aus ("Malformed or ambiguous target").
EXPECTED= PASS
PASS|DEFECT= PASS
EVIDENCE= Zeile 72-74 in `courier_verifier.py`.

## Fall H: ambiguous target -> FAIL CLOSED
SOURCE= scripts/courier_verifier.py
TEST= implizit
CURRENT_BEHAVIOR= Wenn ein Target "mac windows" ist, wird `remote = True`. Wenn dann ein Artefakt lokal via File-Pfad und ohne Upload geprüft werden soll, wird es mit `"FAIL"` abgelehnt (Zeile 97: "not opening remote paths").
EXPECTED= PASS
PASS|DEFECT= PASS
EVIDENCE= Zeile 97-99 lehnt lokale Verifikation bei Remotes ab.

## Additional Checks Evaluated
- stale artifact from earlier run: Abgefangen durch den serverseitigen Upload (neue `artifact_id` generiert) oder durch strikten Path+Hash-Match.
- wrong path but correct hash: Abgelehnt, da der Loop über den exakten Dateinamen läuft (`expected_art.get("path") == art.get("path")`).
- correct path but wrong bytes: Abgelehnt durch Hash-Fehlschlag (F).
- duplicate artifact entries: Vom Verifier Loop als einzelner Fail oder Success behandelt, letztlich durch `Omission Bypass` geschützt, falls das Original verdrängt wurde.
- missing artifact: Abgelehnt (siehe C).
- verifier/result artifact mismatch: Der Verifier operiert direkt auf dem `result` Payload und validiert dieses gegen `task`.
