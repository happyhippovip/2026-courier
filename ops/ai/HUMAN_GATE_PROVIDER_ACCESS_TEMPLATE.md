# Provider Access Human Gate Template

HUMAN_GATE_ID=
TYPE=PROVIDER_ACCESS
STATUS=OPEN
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
CREATED_AT=

Rules:
- No worker changes account, login, plan, billing, token, API key, or auth automatically.
- One gate per unique limit fingerprint.
- Other authorized work continues.
- Close gate only after a human action or a durable provider-state change.
