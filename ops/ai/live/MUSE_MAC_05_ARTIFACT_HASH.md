# MUSE MAC WINDOW 5 — Artifact Proof Chain QA
- BASE=bd539f188d19665d16f1b840d7a74009c4c0d4ac
- GATE: PRE_CODEX_STATE=DURABILITY_PENDING, AUTHORITATIVE_READY=NO (ops/ai/GATE_STATE_CURRENT.md) — kein Re-Validation, kein Gate-Touch
- DATE=2026-09-28
- MODE=QA prep-only (read-only Code-Reads + /tmp-Probes; kein Server-Boot, keine Source-Edits, LEDGER_WORK=SKIP)
- PROBE=/tmp/muse_mac05_probe.py → 25/25 gegen echten Code (ArtifactStore, courier_verifier, integration_contract)
- NEIGHBORS=tests/test_artifact_store.py + tests/test_artifact_upload_flow.py → 55/55 grün
- REUSE=ops/ai/live/MAC09_ARTIFACT_CHAIN.md (Skelett, fremd — nur gelesen, nicht verändert)

## Kette (8 Stufen, code-grounded)
1. task-owned expected hash: `task.expected_artifacts[path]` / `task.expected_sha256` — server-seitig, nie Worker-Payload (`scripts/courier_verifier.py:78`)
2. dispatch: `prepare_task` mint `attempt_id/dispatch_id/worker_id/run_id` (`scripts/integration_contract.py:43-63`)
3. worker artifact result: `verify_result` hasht Datei-Bytes selbst, `result-{canonical_hash}` kanonisch (`integration_contract.py:66-111`)
4. server stored bytes: `ArtifactStore.put` hasht Bytes selbst, content-adressiert `blobs/xx/sha` + write-once Record (`scripts/artifact_store.py:85-116`)
5. server hash: `read_bytes` + `check_reference` (Bindungsfelder + name + sha + size) (`artifact_store.py:124-144`)
6. verifier decision: Server-Kopie re-hashen, gegen task-expected prüfen, remote-Pfade nie öffnen (`courier_verifier.py:54-92`)
7. reconcile: `/tasks/result` → RESULT_RECEIVED (shape+Referenz-Check, `:375-383`), `/tasks/verify` PASS → RECONCILED (`server/app.py:466-515`)
8. proof evidence: `validate_durable_result` Form-Check (hex-Fingerprints, Pfad-Guards posix+win) (`integration_contract.py:114-172`)

## Falsifikation (6 Fälle, ausgeführt — keine PASS-Annahme)
- correct bytes: put→get→`verify_uploaded_artifact`=ok + `check_reference` ok → CHAIN_HOLDS
- wrong bytes: Upload mit falschem `claimed_sha256` → 400 `uploaded bytes do not match the claimed sha256`; Verifier gegen task-expected → FAIL `Hash mismatch against expected_sha256`
- missing artifact: leere Liste → FAIL `No artifact evidence`; fehlende Datei → `ContractError: missing expected artifact`; unbekannte ID → `ArtifactError: unknown artifact_id`
- worker expected-hash spoof: ref-sha≠Server-Bytes → `ArtifactError: artifact reference does not match stored record`; `verify_uploaded_artifact` → `(False, hash mismatch)`; task-expected liegt server-seitig — Worker kann es nicht überschreiben (`courier_verifier.py:78` liest `task`, nicht `result`)
- worker omission: Teilmenge von expected → FAIL `Result is missing expected artifacts`; SUCCESS ohne Evidence → `ContractError: successful result requires artifact evidence`
- ambiguous target: absolut/Drive/UNC/`..`/NUL/leer → `is_safe_artifact_name`=False + Upload-400; Cross-Dispatch-Ref → `ArtifactError: artifact dispatch_id mismatch`; Result mit fremder dispatch_id → `ContractError: dispatch_id mismatch`

## BACKUP: Evidence-Fingerprint-Portabilität Windows→Mac
- `artifact_id` = sha256 kanonisches JSON (binding+name+sha, sort_keys) → deterministisch, host-unabhängig (Probe: identisch für gleiche Inputs)
- `result_id` = `result-{canonical_hash(sort_keys)}` → portabel; beide Regex-gegated (`art-[0-9a-f]{64}`, `[0-9a-f]{64}`)
- FINDING (read-only, fremde Dateien unberührt): Peer-Checkpoints enthalten Host-Strings (`/Users/user/...`, teils `Darwin`) — z.B. `ops/ai/live/MAC05_RUN1_EVIDENCE.md`, `MAC01/02/03/08/11`, `MUSE_MAC_03/04`. Diese Datei hier enthält bewusst keine Host-Strings außer der unvermeidlichen Probe-Pfadzeile oben (ausführbar nur lokal).
- REGEL: Evidence-Fingerprints selbst (art-/result-/sha256) sind portabel; umgebende Checkpoint-Texte mit absoluten Pfaden sind es nicht — Fingerprint-Zeilen maschinell vergleichbar halten.

DO_NOT_REPEAT_FINGERPRINT=sha256-musemac05-artifact-chain-qa-01
NEXT_EXACT_ACTION=MAC10-Schema-Sample + Replay-Abfrage schließen; diese Kette nicht erneut prüfen (25/25 + 55/55 belegt).
