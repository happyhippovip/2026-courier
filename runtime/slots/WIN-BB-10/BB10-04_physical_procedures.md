# WIN-BB-10 BB10-04 — 12-case PHYSICAL proof procedures (runbook, shell session)

TREE=fix-cb1-new @ 329abd80 (re-ground on any move). SHELL=DOWN here → these
are UNEXECUTED procedures for a runner session (human or shell-capable
worker). No overlap: no peer filed run-steps (matrices only). Do NOT run
physical RUN_1 from a read-only window — hand to operator/runner.

## Global preconditions (every case)

P0 fresh COURIER_STATE_FILE + empty COURIER_ARTIFACT_DIR (live tree state
holds Q10/Q12 residue — never reuse). P1 keys set + differ
(COURIER_API_KEY, COURIER_VERIFIER_API_KEY). P2 single :8080 binder
(gunicorn -w 1 --threads 4 XOR flask dev). P3 watchdog + verifier + (if
github) dispatcher processes up. P4 ONE worker, console-attached (service
path is evidence-dark — V-PKG7-3), COURIER_ARTIFACT_UPLOAD=1 for cases
1-4/6/8/12, task duration <300s (600-vs-300 hole). P5 record: server rev
(git rev-parse HEAD), state-file bytes before/after, artifact bytes+hashes,
worker console log, verifier log. NO_EVIDENCE_NO_PASS.

## Cases (setup → steps → expected → forbidden)

C1 expected-survives: POST /goals with workflow_plan [{task_id:t1,
target_agent:windows, instruction:"short", artifacts:[{path:e.txt,
expected_sha256:H(expected bytes)}]}]. Claim (worker) → assert claim packet
artifacts[0].expected_sha256 present. Produce e.txt with EXACT bytes →
upload → result → GET /tasks/pending_verification (verifier key) → assert
expected_sha256 present in pending task. Run verifier → expect PASS →
POST /tasks/verify → RECONCILED. FORBIDDEN: editing bytes between steps.
C2 correct-PASS: as C1 with string artifact ["e.txt"]; full loop → PASS →
RECONCILED; assert server blob bytes == worker bytes (sha compare) and
GET /artifacts/<id> (verifier key) returns them; worker key → 401.
C3 wrong-FAIL: as C2, then OVERWRITE server blob file with other bytes
(keep record) → run verifier → expect FAIL (hash mismatch) →
FAILED_VERIFICATION + goal BLOCKED; restore bytes afterward.
C4 worker-expected-rejected: POST /tasks/result with artifacts
[{path:e.txt,sha256:<64hex>,expected_sha256:<64hex>}] → expect 400
(strict key-set contract:155-156). Also POST upload with claimed sha ≠
bytes → 400; claimed size ≠ len → 400 (store:95-98).
C5 omission: (a) UPLOAD lane: upload e.txt, then POST result whose refs
OMIT e.txt (empty or subset) → CURRENTLY ACCEPTED (D-BB-1 defect — after
fix expect 400/FAIL; today record ACCEPT as known-gap evidence, NOT pass).
(b) LOCAL lane (linux task): task dict-artifact with expected_sha256=H(X),
worker produces Y≠X honestly hashed → CURRENTLY verifier PASSes
(BB01-NEW-1 — after fix expect FAIL). (c) REMOTE non-uploaded: upload OFF,
post hash-only ref → run verifier → expect FAIL + local paths untouched.
C6 legacy: string-form artifacts, correct bytes → PASS → RECONCILED
(exactness NOT claimed; consistency only).
C7 malformed-target: call verify_artifacts path via crafted task
(target_capability "weird") + result → expect FAIL; plus claim a target
no worker holds → expect {"task":None} (no dispatch, stays QUEUED).
C8 replay: POST result → 200; rePOST identical → ACK_DUPLICATE + state
bytes UNCHANGED (diff). POST verify PASS → 200; rePOST same verify →
ACK_DUPLICATE. Kill -9 worker mid-RESULT_READY (before post-ACK) →
restart → assert redelivery byte-identical, single execution in logs.
RELOAD leg: kill -9 SERVER between result-200 and resend → restart same
state file → resend → ACK_DUPLICATE (design-safe per BB10-01 I1; pin it).
C9 changed-status: POST SUCCESS → 200; rePOST same ids with status FAILED
(+artifacts [] as required) → expect 409 + stored result UNCHANGED.
C10 changed-worker: register OTHER; POST SUCCESS as MAC-01 → 200; rePOST
identical-but-worker_id=OTHER → expect 409 (9-field live rule; would ACK
under 3-field patch — BB01-4 — so this case guards the mint source).
Also FIRST-result wrong-worker → 400 + stays DISPATCHED.
C11 changed-attempt/dispatch: POST result with attempt_id/dispatch_id ≠
dispatched → 400. Resume(retry) after FAIL → claim → attempt:2 + fresh
dispatch → rePOST superseded-attempt result → 400.
C12 changed-artifact: POST SUCCESS ref sha=H1 → 200; rePOST same ids ref
sha=H2 → 409 + stored preserved (result_id + artifacts unchanged).

## Post-run

Orphan census (ps: no leaked powershell/python from timeouts — PKG-1
orphan accepted-risk). Save state file + artifact dir + logs as the
proof bundle. Reset (fresh state+dir) before any re-run (RUN2).

## Disposition

READ ONLY. Procedures unowned and unexecuted. On execution, map outcomes
back to PKG-C/BB10-01 verdicts case by case; any deviation re-opens the
code verdict it contradicts.
