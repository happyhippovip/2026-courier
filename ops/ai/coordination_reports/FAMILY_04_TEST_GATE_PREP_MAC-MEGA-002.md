# Family 04 Final Test Gate Preparation (MAC-MEGA-002, READ_ONLY, PREP_ONLY)

**Slot**: MAC-MEGA-002 (yields to live peer MAC-MEGA-001)
**Status**: `WAITING_FOR_FINAL_SHA=YES` — prepare only. Do NOT run candidate-sensitive tests against base `4c1e24cc` and call them final.
**Scope bound**: exactly the 5 authorized files (`scripts/courier_verifier.py`, `scripts/integration_contract.py`, `tests/test_artifact_upload_flow.py`, `server/app.py`, `tests/test_p3_server_idempotency.py`). All 8 paths below verified to exist on base.

## Q021 — artifact tests (exact command, run on FINAL_SHA only)

```
python3 -m pytest tests/test_artifact_upload_flow.py -q
```

- Base reference (not final): 25/25 green per POST200-021. Re-run whole file; `SKIPPED_COUNT` must be 0.

## Q022 — idempotency tests

```
python3 -m pytest tests/test_p3_server_idempotency.py -q
```

- Base reference: 8/8 green. Covers identical-replay ACK (200) and changed-status reject (409).

## Q023 — result identity tests

```
python3 -m pytest tests/test_server_integration_contract.py tests/test_integration_contract.py -q
```

- Run whole files (do not freeze `-k` node IDs now; the writer patch may renumber lines). Must include the changed-worker / changed-attempt-dispatch / changed-artifact rejections (POST200 cases 10–12).

## Q024 — compile gate

```
python3 -m py_compile scripts/courier_verifier.py scripts/integration_contract.py server/app.py tests/test_artifact_upload_flow.py tests/test_p3_server_idempotency.py
```

## Q025 — whitespace gate

```
git diff --check
```

- Must be clean. Known base defect for writer to strip: trailing whitespace at `server/app.py:358,511,518,535` (gate §3, file 4).

## Q026 — 12-case matrix contract

- Case list source of truth: `POST200-021_result.md` §Final 12 Case Classification Matrix, as amended by Q027 packet items 1, 2, 9, 10, 12 (`GOOGLE_PRE_CODEX_GATE_2026-09-27.md` §3).
- On FINAL_SHA, bind every row to executed evidence (test node + line, or attested proof). Omission row must cite BOTH sub-cases (empty-list + partial-omission; see FAMILY_01 delta A1).

## Q027 — deduplicated Writer defect packet

- Pointer only, no duplication: `ops/ai/coordination_reports/FAMILY_18_CENTRAL_WRITER_COMPRESSED.md` + `GOOGLE_PRE_CODEX_GATE_2026-09-27.md` §3. Four defects, five files, whitespace strip included.

## Q028 — final SHA gate (exit block template)

```
FINAL_SHA=
BASE_SHA=4c1e24ccc522042af826bc4c2b595daf85d097f9
EXACT_CHANGED_FILES= (exactly the 5 authorized, diff --stat)
TARGETED_TESTS= (Q021+Q022+Q023 outputs, SKIPPED_COUNT=0)
SKIPPED=0
UNEXPECTED_CHANGED_FILES=0
```

- `PRE_CODEX_READY=YES` only when: FINAL_SHA exists, 5-file scope proven, 12-case matrix bound to FINAL_SHA, all targeted tests green, `SKIPPED_COUNT=0`, `git diff --check` clean, zero unresolved causal P0s. Then STOP new analysis and hand to Codex.

## Resource note

- Gate execution is the single heavy job when triggered (`MAX_HEAVY_JOBS=1`); until FINAL_SHA lands, this family costs zero runtime.

DO_NOT_REPEAT_FINGERPRINT=sha256-dbc036af5102ab89
