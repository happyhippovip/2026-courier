# Distilled Lessons Report

Source: [distilled_lessons.json](distilled_lessons.json)

## Overview

The source contains **6 lessons**, all recorded on **2026-09-01 (UTC)**: 3 experiment results, 2 verified facts, and 1 business validation. Recorded confidence ranges from **64% to 99.2%**.

## Key takeaways

- **Test gap detection:** Two experiment records recommend adoption: AST deterministic test gap scanning proposed by GOOGLE_BUILDER, and a test gap detection proposal from DETERMINISTIC_ORACLE. Both report a 0.99 score and 99.2% confidence; the records do not establish a comparison between these two proposals.
- **Multi-account rotation:** Retain the current method. The record cites an unmet evidence threshold or a critical safety challenge without specifying which applied; confidence is 64%.
- **Crash recovery:** Use CanonicalAuthority generation tokens to prevent stale workers from overwriting state.
- **Task deduplication:** Keep completed fingerprints in memory and write through atomically to disk to reduce repeated disk reads.
- **Revenue validation:** The business-validation record supports packaging existing verified engineering capabilities into structured B2B offerings and asset manifests for market validation with zero capital spend and high asset reuse. It does not document realized revenue.

## Lesson details

### Should we use AST deterministic test gap scanning

- **ID:** `LES-1788264749582`
- **Type:** `EXPERIMENT_RESULT`
- **Lesson:** Verdict: ADOPT. Proposal by GOOGLE_BUILDER demonstrably superior (score 0.99) with verified local evidence
- **Confidence:** 99.2%
- **Source role:** `GOOGLE_BUILDER`
- **Verification recorded:** `COUNCIL_DELIBERATION`
- **Applies to:** `DISPATCHER`, `ROUTER`, `GOOGLE_BUILDER`
- **Created at:** 2026-09-01T12:12:29.582697+00:00
- **Recheck trigger:** Not specified.

### Best method for test gap detection?

- **ID:** `LES-1788264757275`
- **Type:** `EXPERIMENT_RESULT`
- **Lesson:** Verdict: ADOPT. Proposal by DETERMINISTIC_ORACLE demonstrably superior (score 0.99) with verified local evidence
- **Confidence:** 99.2%
- **Source role:** `DETERMINISTIC_ORACLE`
- **Verification recorded:** `COUNCIL_DELIBERATION`
- **Applies to:** `DISPATCHER`, `ROUTER`, `GOOGLE_BUILDER`
- **Created at:** 2026-09-01T12:12:37.275939+00:00
- **Recheck trigger:** Not specified.

### Should we automate multi-account rotation?

- **ID:** `LES-1788264757283`
- **Type:** `EXPERIMENT_RESULT`
- **Lesson:** Verdict: CURRENT_METHOD_RETAINED. Challenger failed evidence threshold or critical safety challenge raised -> Current incumbent retained
- **Confidence:** 64.0%
- **Source role:** `RESEARCH_SCOUT`
- **Verification recorded:** `COUNCIL_DELIBERATION`
- **Applies to:** `DISPATCHER`, `ROUTER`, `GOOGLE_BUILDER`
- **Created at:** 2026-09-01T12:12:37.283158+00:00
- **Recheck trigger:** Not specified.

### Crash Recovery Fencing

- **ID:** `LES-RECOVERY-01`
- **Type:** `VERIFIED_FACT`
- **Lesson:** CanonicalAuthority generation tokens prevent stale worker overwrites.
- **Confidence:** 99.0%
- **Source role:** `GOOGLE_BUILDER`
- **Verification recorded:** `DETERMINISTIC_TEST`
- **Applies to:** `DISPATCHER`, `SURVIVAL_ENGINE`, `FAILOVER_COORDINATOR`
- **Created at:** 2026-09-01T12:12:37.289709+00:00
- **Recheck trigger:** Not specified.

### In-memory task deduplication cache with atomic flush

- **ID:** `LES-DISPATCH-CACHE-01`
- **Type:** `VERIFIED_FACT`
- **Lesson:** Keep completed fingerprints in an in-memory set with atomic write-through to disk to eliminate read storms.
- **Confidence:** 98.0%
- **Source role:** `GOOGLE_BUILDER`
- **Verification recorded:** `DETERMINISTIC_TEST`
- **Applies to:** `DISPATCHER`, `OPPORTUNITY_QUEUE`
- **Created at:** 2026-09-01T12:35:01.045206+00:00
- **Recheck trigger:** Not specified.

### EXPERIMENT_BEFORE_BUILD_REVENUE_VALIDATION

- **ID:** `LES-MONEY-PIPELINE-VALIDATION-01`
- **Type:** `BUSINESS_VALIDATION`
- **Lesson:** Packaging existing verified engineering capabilities into structured commercial B2B offerings and asset manifests enables immediate market validation with 0 EUR capital spend and high asset reuse.
- **Confidence:** 95.0%
- **Source role:** `GOOGLE_PRIMARY_BUILDER`
- **Verification recorded:** `MONEY_MACHINE_PIPELINE`
- **Applies to:** `ALL_REVENUE_CANDIDATES`, `B2B_OFFERINGS`
- **Created at:** 2026-09-01T13:36:50.456102+00:00
- **Recheck trigger:** Not specified.

## Evidence limits

Confidence and verification labels above are reported metadata from the source, not independent validation performed for this report. The JSON contains no underlying test outputs, experiment artifacts, or commercial results. All six recheck triggers are empty; no review conditions or schedule are recorded.
