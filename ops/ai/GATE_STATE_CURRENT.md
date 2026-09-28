# Gate State Current — 2026-09-28

Status: DURABLE COORDINATION STATE

PRE_CODEX_STATE=VALIDATING
REPORTED_PRE_CODEX_READY=YES
REPORTED_FINAL_SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf
BASE_SHA=4c1e24ccc522042af826bc4c2b595daf85d097f9
REMOTE_GITHUB_RESOLUTION=FOUND_ON_candidate-b-1_AS_34b0a4264bf763bc2a78f761ffba36e47706b2cf
AUTHORITATIVE_READY=NO
REASON=Remote durability is confirmed. Remaining authoritative transition is exact final checklist / Claude-Codex fixed-candidate verdict and any material post-review invalidation. Do not reopen remote-durability work.
NEXT=CLAUDE_CODEX_FIXED_CANDIDATE_CONSUME
MAX_GATE_PERSISTENCE_OWNERS=1

COST_GUARD:
- no duplicate remote-durability validators;
- no Ledger work absent RETEST_TRIGGER;
- candidate-independent prep may continue;
- exactly one fixed-candidate Claude/Codex decision;
- one mutable source writer;
- one physical Mac owner.

INVALIDATION_TRIGGER:
- final SHA changes;
- material source delta after review;
- exact test/evidence fingerprint changes;
- a proven causal defect invalidates the candidate.
