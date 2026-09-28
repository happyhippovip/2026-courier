# MUSE WHAT'S LEFT — Current Checkpoint (READ_ONLY_ADVERSARIAL_QA)

SESSION=cloud-octans (MUSE, MAC) · DATE=2026-09-28 · HEAD=bd539f18 (worktree, read-only)
GATE=PRE_CODEX_STATE=DURABILITY_PENDING, AUTHORITATIVE_READY=NO (not revalidated)
COLLISION_NOTE=Prompt-assigned name MUSE_WHATS_LEFT_CURRENT.md is peer-owned
(foreign checkpoint since ~12:5xZ, untouched). This session-unique file holds
my batch instead — no overwrite, no merge into foreign file.
LINE_NOTE=Worktree HEAD descends from BASE b-1 4c1e24cc; dup-key differs
(HEAD: 6-tuple incl. worker/attempt/artifacts per HNI_08 S1; b-1: 3-field).
Findings cite worktree lines unless marked b-1.
0 executions, 0 source edits, ledger untouched, no PRE_CODEX revalidation.

DONE_WORKBANK=T X C W D(run_id) K V Y
ROUND2=K:tasks/plan sync NO_ISSUE (+received_at narrows F-gap);
V:BLOCKED_OTHER_OWNER (motor absent); Y:EVIDENCE_DOC_DEFECT (RUN_2 sheet unbound template)
DO_NOT_REPEAT=G233/G231/G237 invented states (MUSE_MAC_STATE_TRUTH);
state inventory+transitions (MUSE_SOURCE_TRUTH_CORRECTIONS);
resume-no-clear R1; 6-tuple replay (MUSE_HNI_08); hash authority (MUSE_HNI_07);
artifact chain (MUSE_MAC_05); binding (MAC01_BINDING); F1-F5 (MUSE_MAC_08_PROOF_FREEZE);
12-case trace gap 6/12; register-divergence; peer WHAT_IS_LEFT file (D,E,I,J,P,Q,X,L)

## T — Successor readiness vs actual dispatch: NO_ISSUE (boundary pinned)
- No auto-dispatch/auto-advance/reconcile-tick in `server/app.py` (only
"Stop is sticky" comment :246). `claim_task` (:271-357) is pure pull: scans
`goal.workflow_plan` for QUEUED (:290-291), mints fresh attempt/dispatch
(:339-340), writes plan[idx] AND `state["tasks"]` (:350,355).
- Boundary: B-dispatch evidence must show a claim POST; "server pushed B"
prose is ungrounded. `dispatched_at=time.time()` (:349) is the only
server-side dispatch timestamp.

## X — Worker/Verifier auth separation: NO_ISSUE (fail-closed, proven by read)
- `require_auth` (:21-31): 503 on insecure-default key, else Bearer → 401.
- `require_verifier_auth` (:33-44): 503 when verifier key insecure OR equal
to API_KEY — separation runtime-enforced. `/tasks/verify`+pending (:468,478)
under verifier auth; worker routes under worker auth. Sound.

## C — Error-code matrix: 1 CONFIRMED_SOURCE_DEFECT (minor), rest sound
- 401 auth; 404 unknown goal/worker/task; 409 conflicts; 400 validation;
503 unconfigured/planner.
- DEFECT (C1, low): :149 `duplicate task_id from planner` → 503.
Deterministic planner-data error as "service unavailable" invites pointless
retries; correct class 400 (cf. :123 same condition → 400). Writer-owned.

## W — gemini adapter shadow ledger: CONFIRMED_SOURCE_DEFECT
- `scripts/gemini_worker_adapter.py:77 consume()`: CWD-relative
`central_state.json` (vs server `server/state/central_state.json` /
$COURIER_STATE_FILE, app.py:11), silent fallback to `{"tasks": {}}`.
- Writes `"state": "RECONCILED"` for every consumed task incl. FAILED
(`reconciled_status` holds truth) — collides with server RECONCILED.
Adapter-ledger-as-proof = false green; CWD accumulation = contamination
vector. Adapter-lane owner action.

## D — run_id lifecycle: EVIDENCE_DOC_DEFECT (preventive boundary)
- Claim sets `run_id=None` (:343); `prepare_task` only setdefaults it
(`integration_contract.py:57`); nothing in app.py ever assigns run_id;
`verify_result` identity excludes it. Server run_id permanently None here.
- Boundary: proof cards must never cite server-state run_id. Code harmless.

## K — plan/tasks writer-sync sweep: NO_ISSUE
- All paths sync both copies: claim (same object, :350,355); intake syncs
step status/worker_id/attempts (:407-411); verify syncs step status;
heartbeat syncs both. Bonus: intake stamps `result.received_at=time.time()`
(:397) — receipt time exists server-side; verify time still absent (F-gap
narrowed, stands).

## V — motor backoff: BLOCKED_OTHER_OWNER
- `scripts/courier_motor.py` absent in worktree (only precheck). Bounds live
on another line/owner.

## Y — RUN_2 sheet vs instance: EVIDENCE_DOC_DEFECT
- `RUN_2_RESTART_COMMAND_SHEET.md` commands (`python3 -m src.main`,
`ops.assert_state`, `runs/run_001/...`, ResourceAdmissionController): 0 hits
in server/scripts, no `runs/` dir. Unbound template prose (gate line correct).
Rewrite against claim/resume/reclaim API or label TEMPLATE.

CURRENT_PHASE=PRE_CODEX_DURABILITY_PENDING (pre-POST_CODEX)
CURRENT_GATE=DURABILITY_PENDING / AUTHORITATIVE_READY=NO / single-owner gate
DONE_WORKBANK=T X C W D(run_id) K V Y
NEW_CONFIRMED_DEFECTS=C1 planner-duplicate→503 (app.py:149); W adapter shadow
ledger RECONCILED-collision + CWD-relative central_state.json (gemini_worker_adapter.py:77-95)
NEW_EVIDENCE_GAPS=D run_id always-None boundary; Y RUN_2 sheet unbound template
DISPROVEN=(none this round; T/X/K confirmed sound)
BLOCKED_OTHER_OWNER=G233/G231/G237 voids; F1/F2/R1 semantics; b-3 E1 pin;
C1+W fixes (Central Writer / adapter-lane owner); V motor bounds (motor owner)
STOP_DOING=peer-covered lanes (D,E,I,J,P,Q,X,L per peer file); PRE_CODEX
revalidation; physical runs; source edits; overwriting peer live/ files
OPUS_NOW=YES (11 deduplicated: F1-F5 + trace-gap + G233 + C1 + W + D + Y)
OPUS_QUESTIONS=U1/U2 resend semantics?; G231/G233/G237 void owner?;
b-3 E1 rewrite owner?; C1 400-vs-503?; adapter ledger label fix?;
RUN_2 sheet rewrite owner?
CODEX_NOW=NO (gate pending, FINAL_SHA not durably resolvable)
WINDOWS_OWNER_ACTION=U1/U2 decision; G-voids; b-3 E1 rewrite; C1 + adapter fixes;
RUN_2 sheet rebind; F1-F3 evidence corrections
NEXT_WORKBANK=S(verifier run_loop replay/crash — check vs HNI overlap first);
Z(stale-proof across SHA, b-1-anchored only); E-remaining (run_id exclusion already in D — skip)
CLEAR_SAFE=NO (legal points S/Z remain; checkpoint saved)
DO_NOT_REPEAT_FINGERPRINT=muse-whats-left-cloud-octans-20260928-TXCWDKVY
