# Autonomy shard checkpoint

SHARD=15
STATUS=SHARD_COMPLETE
SUBCASES_DONE=4 (S1 dead-antigravity-arm, S2 self-asserted caps, S3 agent/capability split, S4 precedence)
CONFIRMED_SOURCE_DEFECTS=2 (S1, S2)
EVIDENCE_GAPS=0
DISPROVEN=1 (S3 misroute-by-default)
FIX_PACKETS=2 (FP1, FP2 below)
NEXT_OWNER=server-lane owner (server/app.py + scripts/integration_contract.py; foreign scope — no edit made)
DO_NOT_REPEAT=sha256-autonomy-shard15-caprouting-01

## S1 — Antigravity match arm is dead-by-contract (CONFIRMED_SOURCE_DEFECT)
- `server/app.py:299`: `elif "antigravity" in target ... matched=True`; then
  `:343` sets `target_capability="antigravity"` → `prepare_task`
  (`scripts/integration_contract.py:48-52`) raises ContractError since
  WORKER_IDS keys are exactly {github, mac, windows, linux} (contract :26-31,
  no antigravity) → claim returns 400 (`app.py:346-347`).
- Net: antigravity-targeted tasks can NEVER dispatch; antigravity workers can
  register but starve. Match arm promises what the contract refuses.
- FIX_PACKET FP1: FILES=server/app.py:299 + scripts/integration_contract.py:26-31;
  CAUSAL_BUG=routing match vocabulary ⊋ contract capability vocabulary;
  MIN_FIX=either add "antigravity" to WORKER_IDS with bound worker-id, or
  delete the :299 arm so antigravity fails visibly at match (WORKER_BUSY/None)
  instead of 400-at-claim; TARGETED_TEST=register antigravity-capable worker,
  claim antigravity task → receives task (or documented refusal);
  OWNER=server-lane owner; BEFORE_CODEX=NO, BEFORE_RUN1=YES.

## S2 — Capabilities self-asserted, never validated (CONFIRMED_SOURCE_DEFECT)
- Registration stores arbitrary `capabilities` verbatim
  (`server/app.py:233-241`, zero validation); claim trusts them
  (`:294-299`). Any authenticated worker registering
  ["windows","macos","github","linux"] can claim every lane. Bounded test
  grep: no test rejects unknown/forged capabilities.
- FIX_PACKET FP2: FILES=server/app.py (register_worker);
  CAUSAL_BUG=no allowlist/attestation of capabilities at registration;
  MIN_FIX=validate capabilities against known set
  {github,macos,windows,linux(,antigravity per FP1)} at register, 400 on
  unknown; TARGETED_TEST=register with ["root-everything"] → 400, claim → none;
  OWNER=server-lane owner; BEFORE_CODEX=NO, BEFORE_RUN1=YES.

## S3 — Default-target misroute risk (DISPROVEN)
- Feared: missing target_agent defaults to "linux" (`app.py:292`) and
  misroutes. Refuted: unset target_capability fails `prepare_task` identity
  (`contract :48-50`, all str+truthy required) → 400 fail-closed before
  DISPATCHED. No default-route escape.

## S4 — Match precedence deterministic (NO_ISSUE + note)
- Arms evaluated github→mac→windows→linux→antigravity (`app.py:294-299`);
  mac intentionally maps to worker cap "macos" (`:296`). Multi-keyword
  targets resolve to the earliest arm (e.g. "windows-github" → github).
  Deterministic, test-pinned by lane tests (e.g. p3 :208-250 windows,
  :278-281 macos/high-low). Note only: vocabulary asymmetry mac/macos is
  by-design, not a bug.
