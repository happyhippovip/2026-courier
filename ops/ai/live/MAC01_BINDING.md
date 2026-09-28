# MAC01 Source/Build/Runtime/Config Binding — Checkpoint
- DATE=2026-09-28
- HOST=MAC (`Darwin 25.6.0 x86_64`)
- WORKSPACE=`/Users/user/Downloads/2026-courier`
- MODE=prep-only (keine physische Ausführung: keine RUN_1/RUN_2, keine pytest-Läufe, keine Server-/Port-Bindung, keine State-Writes)
- SOURCE_SPECS=`ops/ai/MAC_EXACT_BINDING_SPECIFICATION_2026-09-28.md` (PPREP-01), `ops/ai/MAC_FINGERPRINT_BINDING_FRAMEWORK_2026-09-28.md` (PPREP-03), `ops/ai/MAC_REPO_RUNTIME_CHECKOUT_READINESS_2026-09-28.md` (PPREP-08)
- GATE=`ops/ai/GATE_STATE_CURRENT.md`: PRE_CODEX_STATE=DURABILITY_PENDING, AUTHORITATIVE_READY=NO

## Status
- [x] Source-Bindung (kandidatenunabhängig)
- [x] Runtime-Bindung (kandidatenunabhängig)
- [x] Config-Bindung (kandidatenunabhängig)
- [ ] Build-Bindung (Methode fixiert, Ausführung erst mit FINAL_SHA — siehe unten)
- [ ] Exact FINAL_SHA (UNBOUND — erst bei authoritative durable)

## 1. Source-Bindung (fertig, kandidatenunabhängig)
- HEAD=bd539f188d19665d16f1b840d7a74009c4c0d4ac (detached)
- TREE_SHA=c13cad631623c3ddeb1461f72d4c37ea0afe4b43
- BASE_SHA=4c1e24ccc522042af826bc4c2b595daf85d097f9 (`origin/candidate-b-1`, lokal auflösbar)
- MERGE_BASE(origin/candidate-b-1, HEAD)=4c1e24ccc522042af826bc4c2b595daf85d097f9 (HEAD ist Deszendent der Base-Linie)
- REMOTE_ORIGIN=https://github.com/happyhippovip/2026-courier.git
- Kandidaten-Scope sauber: `git status --short -- scripts/courier_verifier.py scripts/integration_contract.py server/app.py tests/test_artifact_upload_flow.py tests/test_p3_server_idempotency.py` = leer
- Arbeitsbaum-Dirt liegt AUSSCHLIESSLICH ausserhalb des Kandidaten-Scopes (logs/*.err, scripts/mac_worker/logs/*, website/public, logs/courier_server.*) — nicht angerührt (Fremd-Scope)
- 5 autorisierte Dateien (Worktree, HEAD-Stand), SHA-256:
  - scripts/courier_verifier.py=2fbffc4e42895a357f59dfa2fca36d6ad48236ed295283c3f558b7061d304e20
  - scripts/integration_contract.py=aeb3ab6323711d393640b9849274ac174d451b36a9d474d603ded2e55cfcee9d
  - server/app.py=cd57c7303092f5d50ad41a4e5afa01e6ec1a1cf37641d4d410c30b6a5b96a541
  - tests/test_artifact_upload_flow.py=3d9042359570d12260f85258d7222b2351361b1b8ad477b198d10129ba49f1d4
  - tests/test_p3_server_idempotency.py=084464f3709b482a23484ba4bfaf5943a3db8734757ed609df31be36a4ece002
- COVERED_SURFACE_SHA256=5ddd7c2ec3aa7f5f42051d58c6d031621055de0f9bbf64e6e5805e43afe4b8a1 (Framework-Dimension D, sortierte `pfad:hash`-Konkatenation)

## 2. Build-Bindung (Methode fixiert, Ausführung pending)
- Methode fixiert per PPREP-03: `python3 -m py_compile scripts/courier_verifier.py scripts/integration_contract.py server/app.py`, Exit 0 assert, danach SHA-256 über `__pycache__`-Artefakte
- NICHT ausgeführt in dieser Runde (keine physische Ausführung; kein Build-Artefakt erzeugt, keine `__pycache__`-Writes)
- Ausführung erst gemeinsam mit FINAL_SHA-Bindung (Protokoll PPREP-01 Schritt 5)

## 3. Runtime-Bindung (fertig, kandidatenunabhängig)
- OS=Darwin 25.6.0 x86_64
- INTERPRETER=Python 3.9.13 (`/usr/local/bin/python3`, erfüllt Python-3.9+-Invariante)
- Heavy-Lock `/tmp/courier_heavy_job.lock`: absent (frei, MAX_HEAVY_JOBS=1 einhaltbar)
- Port 8081: deklariert als Staging-Port (Ref: scripts/execute_all_finish_packets.py); Verfügbarkeit NICHT per Bind-Probe geprüft (keine physische Ausführung) — Probe ist Teil der FINAL_SHA-Bindung
- STATE_DIR=server/state vorhanden (`drwxr-xr-x`); Schreib-Probe NICHT ausgeführt (kein Write) — Probe ist Teil der FINAL_SHA-Bindung

## 4. Config-Bindung (fertig, kandidatenunabhängig)
- STAGING_PORT=8081 (physische Validierung RUN_1/RUN_2)
- HEAVY_LOCK_PATH=/tmp/courier_heavy_job.lock, MAX_HEAVY_JOBS=1
- STATE_DIR=server/state (isolierte RUN_1-Läufe: server/state/isolated_run1/)
- CANDIDATE_SCOPE (strikt, PPREP-01 Schritt 3): scripts/courier_verifier.py, scripts/integration_contract.py, server/app.py, tests/test_artifact_upload_flow.py, tests/test_p3_server_idempotency.py
- Whitespace-Gate: `git diff --check` erst gegen FINAL_SHA (pending)

## 5. Exact FINAL_SHA (UNBOUND)
- REPORTED_FINAL_SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf (Gate-Datei) — WEDER validiert NOCH gebunden: AUTHORITATIVE_READY=NO, REMOTE_GITHUB_RESOLUTION=NOT_FOUND_AS_OF_2026-09-28
- Kein zweiter Gate-Validator: keine erneute Kreuzvalidierung dieses SHAs (Cost-Guard, max 1 Gate-Persistence-Owner)
- Binde-Trigger (alle erforderlich): AUTHORITATIVE_READY=YES ODER reported SHA wird remote auflösbar ODER kanonisches Candidate-Bundle publiziert ODER Gate-Evidenz-Fingerprint ändert sich
- Bei Trigger: Protokoll PPREP-01 ausführen (fetch, FINAL_SHA=rev-parse, 5-File-Scope, diff-check, 44+ Tests SKIPPED=0), dann Attestation `ops/ai/wall_results/EXACT_MAC_BINDING_ATTESTATION.json`, dann Build-Bindung (py_compile) + Runtime-Proben (Port-Bind, State-Write-Probe, pytest)

## Nächste exakte Aktion
- Bei Gate-Trigger: PPREP-01-Protokoll gegen das dann-authoritative FINAL_SHA fahren; sonst: keine Re-Verifikation dieser Felder (Fingerprint unten schützt vor Wiederholung)

DO_NOT_REPEAT_FINGERPRINT=sha256-mac01-binding-prep-20260928
