# TASK_28 — Exact Canary A Bytes / Hash

STATUS=DONE (physically computed)

## Canary A Artifact
FILE=/Users/user/Downloads/courier_canary/artifacts/canary_A.txt
CONTENT_HEX=43 4f 55 52 49 45 52 2d 41 32 42 2d 41 0a
CONTENT_TEXT=COURIER-A2B-A\n  (LF newline, 12 bytes)
SIZE_BYTES=12
SHA256=96c1471cc2dfc55d49de5a3279dc927774a84b0f5c5bdc7c5755f19d8de9391c
COMPUTED_BY=sha256sum /Users/user/Downloads/courier_canary/artifacts/canary_A.txt
VERIFIED=YES (physical file)

## Prior Canary "CANARY_OK\n" (isolation proof)
CONTENT_TEXT=CANARY_OK\n  (10 bytes)
SHA256=575114332fb4ccd482dd9ca60dbaccc15b579afeb372f0c92b6f7eefe219049b
USED_IN=A->VERIFY->B isolation proof (RECONCILED confirmed)

## Determinism
Same byte sequence → same SHA-256 → deterministic verification.
No ambiguity, no encoding drift (Mac LF, written by shell echo).

PROVEN=Physically computed and verified.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_29
