# Human Gate Current

Status: NONE

HUMAN_GATE_ID=NONE
TYPE=NONE
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

This file is the stable pointer for the currently active operator-required provider/access decision, if any.

Rules:
- Workers never change account, login, auth, plan, billing, token, or API key automatically.
- One unique provider-limit fingerprint creates at most one human gate.
- Unrelated work continues.
