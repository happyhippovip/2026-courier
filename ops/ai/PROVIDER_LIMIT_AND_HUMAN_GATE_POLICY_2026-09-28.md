# Provider Limit / Human Gate Policy — 2026-09-28

Status: CANONICAL COST/ACCESS POLICY

Purpose:
Handle provider baseline/quota/rate/subscription limits without wasting model calls, changing accounts automatically, or blocking unrelated work.

## Hard boundary

Workers MUST NOT:
- create or discover substitute user accounts;
- change login/account automatically;
- rotate accounts automatically;
- alter billing, plan, payment method, API keys, tokens, or auth state;
- copy credentials between providers/hosts;
- bypass provider limits.

Any such action requires an explicit human action outside the worker.

## Limit classification

When a provider returns a limit/error, classify cheaply and once:

LIMIT_TYPE=
- RATE_LIMIT
- DAILY_OR_PERIODIC_QUOTA
- BASELINE_OR_PLAN_LIMIT
- AUTH_REQUIRED
- PROVIDER_UNAVAILABLE
- UNKNOWN_LIMIT

PROVIDER=
MODEL=
HOST=
ERROR_FINGERPRINT=
RETRY_AFTER_IF_EXPLICIT=
AFFECTED_TASK_FAMILY=

Same ERROR_FINGERPRINT is not repeatedly analyzed by many windows.

## Automatic legal recovery

On a limit:

1. Persist the provider-limit result/fingerprint.
2. Stop admitting new work to the affected provider/model family.
3. Re-route only if an already-authorized alternative provider/model is available and capable under MODEL_HOST_ROUTER.
4. Prefer deterministic local work when possible.
5. Continue unrelated READY tasks on other providers/hosts.
6. Do not repeatedly probe the limited provider.
7. If provider gives explicit retry-after/reset time, persist it and hold that family until then.
8. If no explicit retry time exists, do not burn tokens polling.

## HUMAN_GATE

Create a HUMAN_GATE only when progress materially requires a manual access/account/plan/login decision.

HUMAN_GATE fields:

HUMAN_GATE_ID=
TYPE=PROVIDER_ACCESS
PROVIDER=
MODEL=
HOST=
LIMIT_TYPE=
ERROR_FINGERPRINT=
WHY_HUMAN_REQUIRED=
SAFE_OPTIONS=
CURRENT_WORK_CONTINUES_ON=
BLOCKED_FAMILIES=
UNBLOCK_CONDITION=
DO_NOT_REPEAT_UNTIL=

SAFE_OPTIONS may include only:
- manually retry later;
- manually sign in to an already-owned authorized account;
- manually choose a different already-authorized account/provider;
- manually change a subscription/plan if the human wants;
- leave provider disabled and continue elsewhere.

Workers do not execute those actions.

## Continue-by-default

A provider limit is NOT a global stop.

After recording HUMAN_GATE:
- keep other legal READY work running;
- use Google/Muse/Sonnet/Opus/local deterministic work according to router and availability;
- preserve claims/results;
- do not duplicate blocked tasks.

Only become TRUE_IDLE when no legal work remains across all currently available providers/hosts.

## Cost rule

Do not spend paid/high-cost model calls merely to diagnose a known provider limit.
One cheap classification per new error fingerprint is enough.
