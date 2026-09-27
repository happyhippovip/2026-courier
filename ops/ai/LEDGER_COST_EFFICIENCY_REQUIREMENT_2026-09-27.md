# Courier Ledger Cost-Efficiency Requirement — 2026-09-27

## Purpose
Courier must optimize for **verified useful work per unit of AI/resource cost**, not for maximum agent activity.

## Product law
> Use the least AI, token, process, memory, and human-relay cost that can safely produce the required verified result.

This extends, and does not replace, CONTINUE_BY_DEFAULT, FEATHERLIGHT_BY_DEFAULT, NO_EVIDENCE_NO_PASS, NO_BUSYWORK, DUAL_SURFACE_TRUTH, and the existing adaptive wall / Ledger requirements.

## Ledger accounting
For every logical work item, preserve enough provenance to distinguish:
- requested
- admitted
- active
- waiting
- guarded
- result_received
- verified / reconciled
- stopped / blocked

Logical wall size (1..37) MUST NOT imply that the same number of expensive model processes are resident or running.

## Cost and waste signals
Where provider/runtime data is available, record or derive:
- provider/model and billing mode when safely identifiable
- requests/turns
- input tokens
- cached input tokens
- output tokens
- estimated/actual provider cost, clearly distinguished
- retries and reruns
- duplicate work suppressed
- prior evidence/context reused
- human relay avoided
- terminal outcome, especially RECONCILED vs merely RESULT_RECEIVED

Secrets, API keys, credentials, raw private prompts, and sensitive billing identifiers MUST NOT enter the Ledger.

## Admission policy
Before spending a heavy slot, Courier should ask from machine-readable state:
1. Is the work already done and evidenced?
2. Is another owner already working the same mutable scope?
3. Can existing evidence/context/cache satisfy the need?
4. Is this work blocked on an external dependency?
5. Is a cheaper/lightweight/read-only route sufficient?
6. Does the device have measured headroom?

If not useful now, WAIT/GUARD rather than create busywork.

## Customer-facing efficiency
Courier should eventually expose understandable efficiency facts such as:
- cost per verified/reconciled result
- tokens per verified result
- duplicate/rerun work avoided
- cache/reuse benefit where measurable
- active vs waiting/admitted slots
- resource headroom and why work was throttled

Do not claim a percentage saving until a controlled baseline and Courier run measure it.

## Adaptive devices
A low-end device may admit only one useful slot. A stronger device may admit more. Customers retain the logical wall capability, while admission adapts to measured CPU/memory/swap/provider quota/cost headroom.

Bigger wall = more useful verified throughput when resources permit; never automatically more noise, resident processes, token burn, or duplicated analysis.

## Measurement plan
Create a comparable baseline for representative work:
A. unmanaged/multi-agent run
B. Ledger-governed Courier run

Compare equivalent goals and evidence requirements using:
- total cost
- token/request totals
- elapsed time
- reruns/duplicates
- human interventions
- count of RECONCILED verified outcomes

Only measured deltas may become savings claims.

## Current motivating observation
A development dashboard observation on 2026-09-27 showed a 7-day aggregate of approximately 10.1k requests, 862M input tokens, 7.8M output tokens, and $5.88 spend. Treat this only as an internal motivating observation, not as proof of Courier savings. It highlights why token volume, repeated context, duplicate analysis, and verified-output efficiency should be measurable.

## Implementation boundary
This requirement is coordination/product doctrine. It MUST NOT expand the currently frozen final correction source scope or delay the canonical proof path. Instrumentation/product implementation follows through separately scoped work after the current proof gate is green.
