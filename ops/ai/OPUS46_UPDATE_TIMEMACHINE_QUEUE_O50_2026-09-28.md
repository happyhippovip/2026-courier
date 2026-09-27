# O50 — Update/Time-Machine Architecture Review

Status: OPUS_4_6 / C4 / READ_ONLY
Rules:
- RESULT_REUSE_FIRST=YES
- NO_BROAD_REPO_SCAN=YES
- NO_DUPLICATE_REVIEW=YES
- NO_IDLE_ANALYSIS=YES
- NO_BUSYWORK=YES
- UNKNOWN stays UNKNOWN
- no application-source edits
- no Codex invocation
- no physical RUN_1/RUN_2
- unchanged PRE_CODEX fingerprint is not work
- deterministic C0/C1 work must be routed away from Opus
- one live claim per task
- provider limit -> persist once, stop probing, route through provider-limit recovery


Purpose: independently pressure-test the future update/recovery design without implementing it before Core + positive pilot.

Tasks:
O50-01 Release-manifest authority model
O50-02 Source/build/runtime identity transition semantics
O50-03 Atomic activation / partial-install failure semantics
O50-04 Last-Known-Good selection rules
O50-05 Rollback safety with state migrations
O50-06 Time-Machine history completeness
O50-07 Update revocation semantics
O50-08 Dependency rollback compatibility
O50-09 Weekly vs monthly vs emergency channel boundaries
O50-10 Offline/bundled update trust semantics
O50-11 Multi-host update consistency
O50-12 In-flight work preservation during update
O50-13 Final O50 synthesis

Done per task:
- material invariant/ambiguity only
- smallest later design action
- no implementation
- no duplicate of O49 if already settled
