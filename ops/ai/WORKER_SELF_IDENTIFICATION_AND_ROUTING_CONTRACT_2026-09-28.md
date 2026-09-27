# Worker Self-Identification + Routing Contract — 2026-09-28

Status: REQUIRED BEFORE CLAIM

Every model/CLI window must perform a cheap self-identification before claiming work.

## Required self-report

```text
WORKER_ID=
HOST=WINDOWS|MAC|OTHER
PROVIDER=
MODEL_ID=
MODEL_VERSION=
CURRENT_MODE=
AVAILABLE_REASONING_LEVELS=
SELECTED_REASONING_LEVEL=
TOOL_CLASSES=
WRITE_AUTHORITY=
PHYSICAL_RUN_AUTHORITY=
COST_CLASS=FREE_SUBSCRIPTION|LOW|MEDIUM|HIGH|UNKNOWN
CAPABILITY_CLASS=C0|C1|C2|C3|C4|C5|UNKNOWN
MAX_HEAVY_JOBS=
CURRENT_GATE_FINGERPRINT=
RESULT_REUSE_AVAILABLE=YES|NO
```

Unknown values stay UNKNOWN. Do not invent runtime metadata.

## Before claim: fit declaration

For each candidate task compute/report:

```text
TASK_ID=
TASK_CLASS=
MODEL_FIT=GOOD|ACCEPTABLE|POOR|FORBIDDEN
FIT_REASON=
CHEAPER_CAPABLE_ROUTE=
RECOMMENDED_PROVIDER=
RECOMMENDED_MODEL_CLASS=
RECOMMENDED_REASONING_LEVEL=
RECOMMENDED_HOST=
RECOMMENDED_WINDOW_COUNT=
ROUTE_TO=
```

If MODEL_FIT=POOR or FORBIDDEN:
do not claim.
Persist/return ROUTE_TO and take another eligible READY task.

## Self-routing law

The worker must actively say when another model should do the task.

Examples:
- deterministic hash/test -> ROUTE_TO=C0_LOCAL
- bulk exact queue work -> ROUTE_TO=GOOGLE_CLI/C1
- independent semantic QA -> ROUTE_TO=MUSE/C2
- fixed code review -> ROUTE_TO=CODEX/C3
- convergence judgment -> ROUTE_TO=OPUS/C4
- final source mutation -> ROUTE_TO=WINDOWS_ANTIGRAVITY_C5_WRITER
- physical RUN -> ROUTE_TO=MAC_ANTIGRAVITY_C5_RUNNER

## Settings advice

When the current provider exposes a reasoning/thinking selector, the worker must recommend the minimum sufficient level:

DETERMINISTIC / extraction:
LOW

routine structured reasoning:
NORMAL

independent semantic QA:
MEDIUM

difficult convergence/code gate:
HIGH

Do not use HIGH merely because it is available.

If the provider does not expose such a setting:
RECOMMENDED_REASONING_LEVEL is advisory only.

## Human-facing routing output

When a task needs a different worker and no automatic router can dispatch it, output exactly one compact block:

```text
ROUTE_REQUIRED=YES
WHERE=<host>
PROVIDER=<provider>
MODEL_CLASS=<class>
SETTING=<reasoning/mode>
WINDOWS=<count>
TASK=<task id/title>
WHY=<one sentence>
PROMPT_REF=<durable prompt/task path>
```

Do not make the human relay normal result content.

## Cost-safe behavior

Self-identification should be cheap and cached per runtime/session fingerprint.

Do not repeatedly ask the model to introspect itself every task.
Reuse until:
- model/version changes
- provider changes
- tools/permissions change
- host changes
- mode/reasoning setting changes
