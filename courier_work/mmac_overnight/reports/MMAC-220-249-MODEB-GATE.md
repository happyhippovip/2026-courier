# MMAC-220 — #249 HIGH gate re-verified on current head (read-only)

Mode-B self-attestation STANDS on head 0ffca8bc and is now line-grounded:
engine `_execute_mode_b` bridge path -> PASS + model_invoked/model_driven True;
bridge is local-only (no network/model imports; file+print hooks only);
test file lines 106-131 assert the flags True, so CI green proves the wrong
property. Merge-gated; owner fix described in result JSON. No patch here
(author's active scope). Swap 89% used -> no local test runs this turn.
