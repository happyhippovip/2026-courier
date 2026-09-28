# Google Windows — 20 Window Execution Plan — 2026-09-28

Current durable phase:
- Ledger complete
- PRE_CODEX_STATE=DURABILITY_PENDING
- AUTHORITATIVE_READY=NO
- exactly one gate persistence owner

## Window allocation

1. WINDOWS_SELFTEST_CONTINUOUS_AUTOPILOT — supervisor/relauncher-facing continuous worker
2. WINDOWS_HNI_01_GATE_DURABILITY_SINGLE_OWNER
3. WINDOWS_HNI_02_PRE_CODEX_HANDOFF_STRUCTURE
4. WINDOWS_HNI_03_TWELVE_CASE_EVIDENCE_INDEX
5. WINDOWS_HNI_04_TARGETED_TEST_FINGERPRINT_INDEX
6. WINDOWS_HNI_05_CHANGED_FILE_SCOPE_PACKET
7. WINDOWS_HNI_06_STALE_EVIDENCE_INVALIDATION
8. WINDOWS_HNI_07_RESULT_CACHE_INTEGRITY
9. WINDOWS_HNI_08_CLAIM_LEASE_INTEGRITY
10. WINDOWS_HNI_09_CROSS_HOST_HANDOFF_PACKET
11. WINDOWS_HNI_10_MAC_BINDING_INPUT_PACKET
12. WINDOWS_HNI_11_RUN1_INPUT_PACKET
13. WINDOWS_HNI_12_RUN2_INPUT_PACKET
14. WINDOWS_HNI_13_FAILED_EXECUTION_CONTAMINATION
15. WINDOWS_HNI_14_HUMAN_RELAY_ACCOUNTING
16. WINDOWS_HNI_15_CORE_FREEZE_PREREQUISITES
17. WINDOWS_HNI_16_PILOT_UNLOCK_PACKET
18. WINDOWS_HNI_17_PRODUCT_SHELL_GATE_PACKET
19. WINDOWS_HNI_18_MOTOR_RELIABILITY_REGRESSION
20. WINDOWS_HNI_19_PROVIDER_HANDOFF_CONTINUITY

Keep WINDOWS_HNI_20_FINISH_ROUTER as the replacement prompt when any specialist window finishes.

## Rules

- Window 2 is the only gate persistence owner.
- If another live owner already exists, Window 2 must not duplicate it and should route to HNI_20.
- Windows 3-20 must not revalidate unchanged PRE_CODEX.
- Ledger is not reopened without a durable RETEST_TRIGGER.
- Each window claims one unique task before analysis.
- RESULT_REUSE_FIRST.
- MAX_HEAVY_JOBS=1 on the Windows host.
- Physical RUN_1/RUN_2 stay on Mac after their gates.
- Codex remains exactly one HIGH review after authoritative PRE_CODEX READY.

## When a window finishes

Immediately replace its prompt with:
ops/ai/windows_post_ledger20/WINDOWS_HNI_20_WINDOWS_FINISH_ROUTER_PROMPT.txt

The router should:
harvest -> identify earliest unfinished post-Ledger Windows family -> claim unique work -> execute -> persist -> continue.

## Gate transition

When PRE_CODEX_STATE becomes READY and AUTHORITATIVE_READY=YES:
- Window 2 stops gate persistence
- one Google window runs TODAY_PRE_CODEX_HANDOFF_ASSEMBLER
- then exactly one Codex HIGH
- other Google Windows windows continue cache/handoff/run/core-freeze prep without duplicating Codex

## After Codex green

Windows becomes support/harvest/continuity plane while Mac owns:
exact binding -> RUN_1 -> RUN_2.

Google Windows continues:
result harvesting, cross-host packet integrity, evidence indexing, Core Freeze prep, pilot packet prep when unlocked.
