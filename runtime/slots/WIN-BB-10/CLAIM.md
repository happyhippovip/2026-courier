# WIN-BB-10 CLAIM

MISSION=COURIER_WINDOWS_BACKBONE_LONGRUN_WORKER_V3
SLOT=WIN-BB-10 (role-consistent claim; see VACATE note)
ROLE=TARGETED_TEST_GAP_AND_INTEGRATION_CHECK (primary)
HOST=WINDOWS | MODE=READ_ONLY_REPORT | SHELL=DOWN (10th identical sandbox-setup failure, OBSERVED, no repair)
HEAD=fix-cb1-new @ 329abd80 | CANONICAL_BASE=candidate-b-1 @ 4c1e24cc | FINAL_SHA=ABSENT
SESSION=01a0e2dc-65df-7101-9126-ffb083be8dcf

VACATE NOTE: this window was pre-assigned WIN-BB-01 but found it LIVE-occupied
(CLAIM.md + state.json WORKING + BB01_PKG-A/B/C, foreign peer, same role).
Per STRICT no-steal + saturation rule, moved to WIN-BB-10: WIN-BB-02..09 have
zero files BUT their roles are live-owned (BB-02 matrix = peer PKG-C, BB-09 =
peer PKG-B, BB-03/04/05/07/08 = filed peers + PAYG WIN-08 baseline adopted).
BB-10 is the highest-value unowned role. Peer files untouched. Own-slot writes
only (runtime/slots/WIN-BB-10/); source tree read-only; WORKROOT unreachable
(os error 2) so evidence lives here + memory.

WORK LOG:
- BB10-00: slot move + dedupe vs WIN-BB-01 PKG-A/B/C (this claim). Adopted peer
  case-4 reading; D-BB-1 vs BB01-NEW-1 ruled DISTINCT (coverage vs local-value).
- NEXT: BB10-01 consolidated test-gap + integration-check package.
