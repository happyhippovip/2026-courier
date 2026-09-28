# MUSE MAC Window 3 — Mac Exact Binding (semantic check)

Slot: MUSE_MAC_03_BINDING (unique C2 claim, trusted-hash/binding semantics).
Host: Mac, repo `/Users/user/Downloads/2026-courier`, HEAD `bd539f18`.
FINAL_SHA is NOT authoritative (gate DURABILITY_PENDING, remote NOT_FOUND) —
nothing below invents a binding. Candidate-sensitive fields are WAITING.
BACKUP= (no backup taken; read-only check, no binding-relevant mutation).

## 9-dimension status

- source fingerprint: WAITING. Matrix claims FINAL 34b0a426 (=HEAD~1 locally) but gate
  says remote-unresolvable; origin/candidate-b-1=4c1e24cc. No authoritative bind.
- build fingerprint: WAITING. Matrix BUILD_ID says Darwin-24.3.0, host docs say
  Darwin 25.6.0; `__pycache__` fingerprints never captured for a locked candidate.
- runtime fingerprint: WAITING. Matrix `/usr/local/bin/python3` vs live PID 606
  `/Library/Frameworks/...3.9`; PORT_PLAN cites PID 69407, live is 606.
- config fingerprint: WAITING (matrix `8b9d...` derived from un-gated candidate).
- state directory: PREPPED-EMPTY, unbound. Fresh `server/state/isolated_run1+2/` (run IDs
  75821131 / 9783F60C); competing conventions: canary workspaces vs `/tmp/courier_run*_SHA`.
- artifact directory: same — fresh isolated dirs empty; `server/state/artifacts/{blobs,records}` production, untouched.
- log directory: unbound. Matrix claims `canary_run1/logs`, absent on disk.
- process identity: mapped, unbound. :8081 free; :8080=PID 606 (PPID 1, PGID 606, SHA unknown) protected.
- run identity: prep IDs minted, explicitly NOT proof-bound (WAITING until boot).

Honest placeholders (good): `RUNTIME_SOURCE_BINDING.json` + RUN1/RUN2 templates keep
`{{FINAL_SHA}}` — correctly unbound, reused as-is.

## False-binding risks (6)

1. Matrix asserts 34b0a426-bound hashes/BUILD/CONFIG while gate denies authority → reading it as proof is false binding.
2. Three state/artifact/log conventions (canary_* vs isolated_run* vs /tmp/courier_run*_SHA); evidence in one is unbound in the others.
3. Stale matrix paths: `canary_run2/` absent, `canary_run1/logs/` absent.
4. Stale build/runtime IDs (Darwin 24.3.0 vs 25.6.0, python path, PID 69407 vs 606).
5. Live PID 606 of unknown SHA — assuming it equals any candidate is false binding.
6. `handoff.json` is revenue task-003 (bdadda27, PR#10, human_merge_required) — no Windows→Mac candidate handoff artifact exists; handoff dimension unbound/stale.

## Windows→Mac handoff check

No dedicated Windows→Mac binding handoff found (only revenue `handoff.json`, unrelated lineage).
Stale: matrix PORT/PID/build strings. Unbound: FINAL_SHA, 5-file hashes, config, process/run identity.
Next owner binds only after gate flips to durably resolvable + single persistence owner publishes.

## Result block

TASK_ID=MUSE_MAC_03_BINDING
FAMILY=trusted-hash/binding
STATUS=QA_DONE (9 dims checked, 6 risks, zero bindings invented, zero kills, zero ledger writes)
RESULTS_REUSED=EXACT_MAC_BINDING + BINDING_SPEC + FINGERPRINT_FW + RUN1/RUN2 templates (read only)
FINDING=4+ false-binding risks confirmed (6 filed); all candidate fields WAITING
MISSING_EVIDENCE=authoritative FINAL_SHA + single-owner binding attestation
NEXT_EXACT_ACTION=hold; re-run this check only after gate invalidation trigger fires
DO_NOT_REPEAT_FINGERPRINT=MAC03-binding-WAITING-20260928-bd539f18
