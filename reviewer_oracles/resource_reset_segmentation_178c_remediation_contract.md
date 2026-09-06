# 178C Remediation Contract — Authoritative Reset Segments

## Scope

This contract closes only the reset-segmentation authority findings from the
independent 178C review. It does not change provider quotas, account-pool
routing, spend policy, or historical observations.

## Current unsafe boundary

`HistoricalResourceObservation` is an in-memory value object. A caller can
replace its `five_hour_segment_id` or `weekly_segment_id` before asking the
manager for a delta. Therefore a caller-controlled object must never be the
authority for reset membership or temporal ordering.

## Required implementation properties

1. Delta APIs that operate on persisted observations must resolve both supplied
   `observation_id` values against one canonical immutable observation registry.
   The resolved canonical records, not caller-provided fields, determine
   provider, account pool, model pool, segment membership, timestamps and
   remaining percentages.
2. If an ID is absent, duplicated, or the caller object's immutable fields do
   not match the canonical record, reject fail-closed with a typed validation
   error. Do not silently repair or calculate a delta.
3. A five-hour delta is allowed only when canonical provider, account-pool,
   model-pool and `five_hour_segment_id` all match. A weekly delta applies the
   corresponding `weekly_segment_id` rule.
4. A delta requires two parseable, ordered timestamps. `UNKNOWN`, malformed or
   equal/out-of-order timestamps return `NOT_COMPARABLE` (or a typed
   fail-closed error); they must not yield a numeric delta.
5. Historical observations remain preserved verbatim. Any registry digest or
   immutable index is derived from them and must not rewrite them.

## Required adversarial acceptance cases

* Forging the Google reset observation into the pre-reset five-hour segment is
  rejected; no `+53` result is produced.
* Forging the OpenAI post-reset observation into the pre-reset segment is
  rejected; no `+83` result is produced.
* An unknown-timestamp observation cannot produce a numeric delta.
* Genuine same-segment, ordered canonical observations still calculate a delta.
* Cross-provider, cross-account, cross-model and cross-reset comparisons remain
  rejected.

## Evidence required for closure

Run the existing resource tests plus the 178C reviewer oracle after changing
its expected adversarial outcomes from demonstrable bypasses to fail-closed
rejections. Record only deterministic local test evidence; no provider API,
account switch, OAuth, spend or external write is needed.
