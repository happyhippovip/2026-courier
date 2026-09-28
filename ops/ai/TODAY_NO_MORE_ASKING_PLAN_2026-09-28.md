# Courier — Today No-More-Asking Wall Plan

Date: 2026-09-28
Status: ACTIVE
Goal: keep all Muse/Google windows useful without duplicate analysis or token-burning idle loops.

## Verified current durable facts

- Published recovery branch: runner-recovery/e9b4f15f-20260928
- Exact published SHA: e9b4f15f8bc45be3d2bc2d9ab4f3c8ead7a77939
- Compare against candidate-b-1 34b0a4264bf763bc2a78f761ffba36e47706b2cf: 12 commits ahead, 0 behind.
- Exact branch is identical to e9b4f15f8bc45be3d2bc2d9ab4f3c8ead7a77939.
- Current phase: BEFORE_RUN1 / pre-physical convergence.
- Read-only preparation is substantially converged. Do not recreate old MUSE_DIRECT_65_96 or MUSE_FUTURE_97_144 work.
- Key remaining classes: exact-byte convergence, verifier/key-custody independence, N1/N2, transition/result provenance, RUN2 desimulation, final writer pass, exact Mac binding, RUN1, RUN2, Core Freeze.

## Global rule

No 1000x repeated prompts.
No watch/sleep loops that consume full context on unchanged state.
Use static sharded lanes for read-only work.
One sole writer only.
One physical owner only.
After writer SHA change, invalidate only affected evidence.

## Mac Muse lane map 01-30

01 published-delta inventory
02 runner dependency completeness
03 real-producer callgraph
04 real-effect boundary
05 verifier-key custody
06 result provenance
07 artifact provenance
08 independent verifier path
09 task expectation authority
10 duplicate/replay identity
11 retry generation freshness
12 stale identity rejection
13 state persistence
14 restart/no-replay
15 worker liveness/reclaim
16 process PID/PGID safety
17 port/state isolation
18 resource admission
19 verify->reconcile
20 NEXT_READY->B
21 zero-human relay
22 RUN1 exact-once
23 RUN1 fail stickiness
24 RUN1 proof witnesses
25 RUN2 desimulation
26 RUN2 restart proof
27 stale dispatch/result/worker/attempt
28 Core Freeze unknown burn
29 cross-host evidence durability
30 pilot runtime prep

## Windows Muse lane map 01-24

01 exact-byte diff review
02 N1 stale execute_run1 reference
03 N2 RUN1->RUN2 gate
04 exit-code truth
05 transition sourcing
06 DONE->SUCCESS rewrite
07 relay count truth
08 verifier-key custody
09 verifier-artifact contract
10 artifact expected authority
11 result replay
12 retry/stale generation
13 server state durability
14 worker liveness
15 successor motor
16 RUN1 targeted test gaps
17 RUN2 targeted test gaps
18 run2 desimulation source packet
19 process/resource gaps
20 cross-host evidence transport
21 proof-card false-green audit
22 Core Freeze blocker matrix
23 writer-packet synthesis
24 post-writer invalidation plan

## Google lane map

Google Windows: same Windows lanes read-only unless explicit SOURCE_WRITE.
Google Mac: same Mac lanes with emphasis on binding/witness/process safety.

## Serial owner order

1. Read-only exact-byte convergence.
2. Sole Windows Writer closes only confirmed packets.
3. New SHA read-only convergence.
4. Mac exact binding.
5. Single Physical Owner RUN_1.
6. If RUN_1 PASS: RUN_2.
7. Core Freeze.
8. Minimum real pilot.
9. Product Shell only after positive pilot evidence.

## Stopping rule

A read-only window may stop when its assigned lane is complete and no unique authorized lane remains. This is not failure. Do not burn tokens to keep it artificially alive. Reuse the window only after a real state change or with a different unfinished shard.
