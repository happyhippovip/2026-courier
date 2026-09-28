# MUSE SUBAGENT TURBO — parent result (no children spawned)

FAMILY=REPLAY_IDENTITY (chosen: richest filed evidence; RUN1_WITNESS/RUN2_RESTART
have zero physical runs → unanswerable read-only; EXACTLY_ONCE overlaps
REPLAY_IDENTITY core and carries crash-window residuals needing execution).
SPAWN_DECISION: 0 subagents started. Existing evidence answers the core question
decisively (rule: "Subagents nicht starten, wenn vorhandene Evidence die Frage
bereits eindeutig beantwortet"); A/B/C re-derivation would be duplicate cost.

SOURCE_TRUTH=server/app.py:389-392 (HEAD ae0030c8): 6-field stored-match
(dispatch_id,result_id,status,worker_id,attempt_id,artifacts) → ACK_DUPLICATE
(:390) BEFORE terminal-state 409 (:391-392). Replay path performs zero
execution — pure acknowledgement. Corroborated by MUSE-HNI-08 QA (S1/S2, same
mechanism) and wall G088/G089/G090 PROVEN (equivalence fields, persistence
boundary, matrix compression).
CONFIRMED=identical-result replay ACKs without re-execution; changed-payload
resend on processed task → 409 conflict (fail-closed).
DISPROVEN="replay re-triggers execution" (no exec call exists on the ACK path).
NOT_CLAIMED=MMAC-027 "5/5 executed probes" (session memory only — no durable
file under courier_work/ in this tree; find empty). Not cited as evidence.
MINIMUM_PROOF=app.py:389-392 + HNI-08 + G088-G090 (all filed, no re-run needed).
MINIMUM_FIX=NONE in C2 scope. Residuals F1/F2 (worker-sensitive ACK width) +
R1 (resume-no-clear replay) are delineated Central-Writer decisions
(BEFORE_RUN1, writer-owned) — explicitly not re-opened here.
OWNER=Central Writer (F1/F2/R1 only); replay core needs no owner.
DO_NOT_REPEAT=sha256-muse-turbo-replay-identity-01; HNI-08-redo; G081-G087 wall
(BLOCKED procedural, GOOGLE lane — untouched); MMAC-027-probe-recall
