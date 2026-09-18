# Physical Acceptance Plan

Physical acceptance is distinct from software tests.

Required eventual proof:

- one reviewed exact SHA,
- exact SHA deployed to canonical Windows runtime,
- actual process identity bound to that SHA,
- OS-owned persistent Motor survives initiating session loss,
- >=10 eligible real tasks,
- >=2 real workers,
- USER_CONTINUE_MESSAGES=0,
- MANUAL_PROCESS_RESTARTS=0,
- DUPLICATE_EXTERNAL_EFFECTS=0,
- result → verification → reconciliation → next task automatically,
- WAITING_PROVIDER isolation,
- unrelated READY work continues,
- waiting task resumes when provider clears,
- durable checkpoint,
- real restart/interruption,
- resume not replay,
- genuine exhaustion,
- CLEAN_IDLE only then.

## Invalid proof

The following do not constitute physical proof:
- mocks,
- synthetic ledgers,
- manufactured counters,
- fixtures,
- substitute proof servers/workers,
- stale evidence from another runtime SHA,
- self-certification,
- same-update evidence.

The harness may observe or safely stimulate the canonical runtime; it may not create the truth it claims to prove.
