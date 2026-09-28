# Muse 21-30 + Supercode Canary — 2026-09-28

Current durable state:
PRE_CODEX_STATE=DURABILITY_PENDING
AUTHORITATIVE_READY=NO

## Muse
Use windows 21-30 for:
21 PRE_CODEX packet consistency
22 test-to-case binding
23 final scope drift
24 trusted-hash bypass
25 duplicate result conflict
26 Mac run-packet completeness
27 restart recovery semantics
28 Core Freeze dependency audit
29 pilot false-start prevention
30 Muse convergence summary

Recommended:
- 10 Muse windows
- each prompt 3-4 queued repeats max
- stop repeating a family once its do-not-repeat fingerprint is complete

## Supercode
Not currently registered/proven in Courier.
Use exactly 1 conservative canary first.

If canary proves C1/C2:
allow 2-4 read-only windows for bounded prep/QA.
Do not give source-write, gate-owner, Codex-replacement, or physical-run authority.

## Order
Muse bulk QA now
-> optional Supercode canary
-> if proven, bounded C1/C2 work
-> Opus 4.6 convergence
-> Codex HIGH exactly once only after PRE_CODEX authoritative READY
-> Mac exact binding / RUN_1 / RUN_2
