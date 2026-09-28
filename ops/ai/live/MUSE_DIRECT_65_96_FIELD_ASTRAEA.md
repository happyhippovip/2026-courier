# MUSE_DIRECT_65_96 checkpoint — FIELD_ASTRAEA (read-only deep work)

OWNER=MUSE / HOST=MAC / DATE=2026-09-28 / SESSION=field-astraea
MODE=READ_ONLY_REPORT. 0 source edits, 0 commits, 0 pushes, 0 test-runs,
0 ledger reads/writes, no git show/fetch, no PRE_CODEX re-validation, no RUN_1/RUN_2.
BASE noting: HEAD=d75e51d4 (Windows Central Writer commits landing); tree has
peer-dirty entries (untouched).

## Entry correction (freshness, this run)
- `ops/ai/MUSE_DIRECT_65_96_2026-09-28.md` still ENOENT.
- Prior SAFFRON claim "0 wall_claims MUSE-65..96" was a grep artefact (pattern
  `MUSE.*(65-96)` misses `G0xx` names). Truth: wall_claims G065..G099 exist,
  wall_results G065..G096 exist. Family queue:
  `ops/ai/MAC_GOOGLE_OVERNIGHT_QUEUE_120_2026-09-27.md:55-66`.
- Census (STATUS lines, read this run): G065-070 PROVEN, G071-087 BLOCKED
  (WAITING_FOR_FINAL_SHA), G088-090 PROVEN, G091-096 BLOCKED
  (WAITING_FOR_FINAL_SHA / READY_FOR_PHYSICAL_RUN).
- Lowest unfinished family: **G071 — Goal->Task expected-hash ownership trace**.
  Then **G072 — Task->dispatch expected-hash propagation trace** (same run).
- G071/G072 wall verdicts left untouched (GOOGLE-owned slots; BLOCKED on
  FINAL_SHA still stands — FINAL_SHA resolution is gate-owner scope, not here).

## FAMILY G071 — 5 NEW subcases (source truth, working tree)

- G071-S1 OWNER-READ (task-only): `scripts/courier_verifier.py:78`
  `task_expected = task.get("expected_artifacts", {}).get(art.get("path")) or
  task.get("expected_sha256")` — expectation sourced EXCLUSIVELY from task.
  No `art.get("expected_sha256")` anywhere on the verifier path (bounded grep
  over scripts/server/tests: only writer is tests + prose). Stale prose
  (POST200-021 case 1, MPREP-03 claim 1, FAMILY_18 doc) describing a
  worker-hash read at :78 does NOT match this tree (writer fix committed).
- G071-S2 SCHEMA-GATE (intake): `scripts/integration_contract.py:152-156` —
  worker artifact dicts must be EXACTLY `{"path","sha256"}` or
  `{"path","sha256","artifact_id","size"}` else ContractError. An
  `expected_sha256` key in worker artifacts is now rejected at intake.
  POST200-021 case-4 defect (line 156 permits injection) is CLOSED in this tree.
- G071-S3 PRODUCER-GAP (new, writer lane): NOTHING in server/, fixtures/,
  schemas/, intake or claim path ever WRITES `task["expected_artifacts"]`
  (bounded grep: zero hits outside verifier+test+prose). `prepare_task`
  (`scripts/integration_contract.py:43-63`, :59) defaults only the
  `task["artifacts"]` NAMES list, never expected hashes. Consequence: the pin
  read at verifier :78 is `None` for production tasks → pin layer silently
  skipped (bytes still enforced via upload path S4). Distinct from the closed
  injection defect: this is the missing producer side. Consistent with
  GLEDGER-108 "OPEN (ownership binding)" note, now anchored to current lines.
- G071-S4 SECOND-PATH (server bytes): `scripts/artifact_store.py:147-159`
  `verify_uploaded_artifact` re-hashes server bytes, checks ref+record+all
  BINDING_FIELDS vs task (`:23` =
  goal_id/task_id/attempt_id/dispatch_id/worker_id). Reads no expected pin,
  trusts no worker hash. Upload gate `:189-191` (name must be in
  task["artifacts"]) + `:194-195` (server re-hash at put) close tampering
  independently of the pin layer.
- G071-S5 TEST-NUANCE (existing evidence, new read):
  `tests/test_artifact_upload_flow.py:143-168`. Step 4 (`:166-168`, "worker key
  ignored") is OVER-DETERMINED: step 3 (`:163`) leaves a stale pin `"f"*64` on
  the task, so the step-4 FAIL is fully explained by the task-pin mismatch at
  verifier :78-82 without isolating worker-key handling. The test proves
  stale-task-pin → FAIL, not worker-key-ignored in isolation. Flag for test
  owner; no test edit made (not my lane).

## FAMILY G072 — 4 NEW subcases (source truth, working tree)

- G072-T1 PROPAGATION-BY-CONTAINMENT: `server/app.py:357`
  `return jsonify({"task": next_task})` — the dispatch payload IS the full
  task dict. No separate dispatch record copies the hash; task["artifacts"]
  (+ expected fields if ever produced, cf. G071-S3) ride along structurally.
  No copy step exists that could drop the pin.
- G072-T2 CLAIM-TIME CONTRACT: `server/app.py:344-348` — `prepare_task`
  runs inside claim before DISPATCHED, fail-closed on ContractError
  (`:346-347`). `prepare_task` copies via `dict(task)` (contract :45),
  preserving any expected-hash fields; defaults identity only (:54-59).
- G072-T3 DISPATCH FRESHNESS: `server/app.py:340` mints
  `dispatch-{uuid4}` per claim BEFORE prepare_task's setdefault (contract
  :55) → always fresh. Stale-resend bounded by 409 path (`:379-380`).
- G072-T4 ATTEMPT BINDING: `server/app.py:338-339` mints
  `{task_id}:attempt:{n}` per claim; BINDING_FIELDS (artifact_store.py:23)
  include attempt+dispatch → task→dispatch→upload chain re-bound every claim.

## Status
G071: 5/5 new subcases done (1 producer-gap → writer lane, rest pins).
G072: 4/4 new subcases done (all pins, no gaps).
Neither family is FAMILY_COMPLETE (wall BLOCKED on FINAL_SHA stands, unowned).

DO_NOT_REPEAT_FINGERPRINT=sha256-muse-direct-65-96-field-astraea-g071-g072
RESUME-TRIGGER: continue at G073 (Dispatch->verification propagation trace);
or gate-owner publishes FINAL_SHA (then re-check S3 producer gap first).
