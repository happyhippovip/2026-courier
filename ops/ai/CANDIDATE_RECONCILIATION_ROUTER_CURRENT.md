# Candidate Reconciliation Router — CURRENT

Status: READ_ONLY ROUTING
Date: 2026-09-28

Use this router whenever GATE_STATE_CURRENT.md says CURRENT_PHASE=CANDIDATE_STATE_RECONCILIATION.

Physical execution is not authorized in this phase.

Slots:

01 CANDIDATE_LINEAGE_AND_SHA_MAP
02 LOCAL_FIXED_COMMIT_FULL_IDENTITY
03 ADOPT_OR_RULE_OUT_DECISION_PACKET
04 CHANGED_FILES_DURABLE_TO_LOCAL_FIXED
05 VERIFIER_KEY_CUSTODY_DELTA
06 RUN2_DESIMULATION_DELTA
07 FINAL_REMOTE_LOCAL_BOUND_EQUALITY_CHECKLIST
08 EVIDENCE_INVALIDATION_MAP
09 ROLLBACK_LKG_MAP
10 NEXT_OWNER_SYNTHESIS
11-30 PARK_UNTIL_CANDIDATE_DECISION

Worker rules:
- read GATE_STATE_CURRENT.md first;
- inspect only the minimum current git/source/evidence required;
- do not repeat old broad review;
- do not edit application source;
- do not perform physical runs;
- reuse unchanged evidence;
- if a decision or write is required, create the smallest exact owner packet;
- if no unique legal work remains, park.
