# Wall Task Packet Schema

Status: REQUIRED CONTRACT FOR MD-FIRST WALL TASKS

Every wall task packet must include these fields.

```text
TASK_ID=
QUEUE_GENERATION=
TITLE=
PRIORITY=P0|P1|P2
ROLE=PREPARE|EXECUTE|VERIFY|HARVEST
TASK_CLASS=C0_DETERMINISTIC|C1_BULK|C2_REVIEW|C3_CODE_GATE|C4_CONVERGENCE|C5_WRITER|C5_PHYSICAL
PREFERRED_PROVIDER=
ALLOWED_PROVIDERS=
PREFERRED_HOST=WINDOWS|MAC|EITHER
MIN_CAPABILITY_CLASS=
MAX_COST_CLASS=
RECOMMENDED_REASONING_LEVEL=LOW|NORMAL|MEDIUM|HIGH|NONE
TASK_FAMILY_PARALLEL_CAP=

DEPENDENCIES=
TRUTH_KEYS=
EXACT_INPUTS=
EXACT_FILES_OR_RESULTS=

ALLOWED_ACTION=
FORBIDDEN_ACTIONS=

READ_BUDGET=
ALLOWED_TEST=
MAX_HEAVY_JOBS=

EXPECTED_OUTPUT=
OUTPUT_PATH=
DONE_CONDITION=

RETEST_TRIGGER=
DO_NOT_REPEAT_FINGERPRINT=

SOURCE_WRITER_AUTHORITY=
HUMAN_GATE_IF=
```

## Requirements

EXACT_INPUTS must be narrow. "Repo" or "everything" is invalid.

READ_BUDGET should normally name either:
- exact files,
- exact result summaries,
- or a small maximum count.

A worker may not broaden scope because it is curious.

DONE_CONDITION must be objectively checkable.

DO_NOT_REPEAT_FINGERPRINT must change only when the material inputs that justify rework change.

RETEST_TRIGGER must be explicit, for example:
- FINAL_SHA_CHANGED
- CONTRACT_VERSION_CHANGED
- TARGET_FILE_FINGERPRINT_CHANGED
- QUEUE_GENERATION_CHANGED

No trigger means completed work stays completed.

## Recommended result format

```text
TASK_ID=
QUEUE_GENERATION=
STATUS=PASS|FAIL|BLOCKED|RETEST_REQUIRED
INPUTS_READ=
COMMANDS_RUN=
TESTS_RUN=
OUTPUT_FILE=
EVIDENCE_REFS=
BLOCKER=
CENTRAL_WRITER_INPUT=
DO_NOT_REPEAT=
NEXT_DEPENDENCY=
NEXT_TASK_CLASS=
NEXT_PREFERRED_PROVIDER=
NEXT_PREFERRED_HOST=
NEXT_REASONING_LEVEL=
NEXT_WINDOW_COUNT=
NEXT_PROMPT_REF=
```

## Invalid tasks

Reject or return to PREPARER when a packet says:
- read everything
- scan the repo
- find useful work
- keep researching
- improve anything you see
- run all tests

unless a specific exceptional policy explicitly authorizes that scope.


## Model-aware routing requirement

Before claim, apply `ops/ai/MODEL_AWARE_WALL_ROUTING_POLICY_2026-09-28.md` and the worker self-identification contract. A capable model without required authority is not eligible. Prefer C0 deterministic execution and the cheapest capable safe provider. Expensive C3/C4 workers require a task packet that explicitly justifies that class.
