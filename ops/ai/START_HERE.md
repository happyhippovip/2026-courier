# COURIER SYMPHONY MUSE — START HERE

This directory is the canonical shared engineering memory for ChatGPT, MUSE,
Google Antigravity, Codex, NEWSY/read-only scouts, and human operators.

CODE_BASE_HEAD: 0c8d1eddacb15dedbebb8406e475917dc2ab1c2b
UPDATED_AT: 2026-09-18T09:23:33+02:00

`CODE_BASE_HEAD` is the last runtime-affecting commit reviewed by this memory
update. Memory-only commits may follow it without invalidating the code binding.

## Startup

1. Read this file.
2. Fetch and verify local HEAD and `origin/release-candidate-integration`.
3. Read `OWNERSHIP_MAP.yaml` and `TEST_MAP.yaml`.
4. Read only the artifact and prepared packet relevant to the assigned task.
5. Inspect only the delta since the packet's `CURRENT_HEAD`.

Do not rediscover documented facts unless newer executable evidence contradicts
them. The historical `.agents/knowledge/*` pack is non-authoritative; it points
here.

## Canonical read order

`MASTER_OPERATING_SYSTEM.md` → `CLOUD_ALIGNMENT_2026-09-18.md` →
`OWNERSHIP_MAP.yaml` → task-specific source/test map → prepared packet.

## Permanent rules

Apply [Better-than-Brief](../../GOAL_REFRAME_BETTER_THAN_BRIEF_RULE.md) to all existing and future plans and handoffs. Preserve original ideas and requirements; make one bounded improvement decision, then execute and verify. Use [the addendum template](BETTER_GOAL_WORK_PACKAGE_TEMPLATE.md) and [prompt experiments](BETTER_GOAL_PROMPTS.md). No executable READY work means checkpoint and worker IDLE without model polling, not global completion.

PACKET FIRST. ONE WRITER. T0 → T1 → T2. T3 BEFORE CODEX. CODEX ONLY WHEN
INDEPENDENCE MATTERS. T4 ONLY AT BOUNDARIES. BLOCKED TASK != BLOCKED PROJECT.
LEDGER LAST. NO FAKE GREEN.

REAL EVENT → DURABLE STATE → EVIDENCE → INDEPENDENT VALIDATION →
SHA/RUNTIME/FRESHNESS CHECK → ACCEPTANCE GUARD → LEDGER.

## Review packet required for Codex

`CURRENT_HEAD`, `COMMITS_UNDER_REVIEW`, `INVARIANTS`, `REPRODUCERS`,
`T2_RESULTS`, `T3_RESULTS`, `KNOWN_ATTACKS`, `FILES_TO_READ`, and
`QUESTIONS_TO_ANSWER` are mandatory. Missing data means `PACKET_INCOMPLETE`.
