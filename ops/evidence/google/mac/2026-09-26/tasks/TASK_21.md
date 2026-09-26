# TASK_21 — Correct expected_sha256 Fixture

STATUS=DONE

## Canonical Canary A Content
CONTENT_BYTES=COURIER-A2B-A\n  (12 bytes: 43 4f 55 52 49 45 52 2d 41 32 42 2d 41 0a)
PHYSICAL_FILE=/Users/user/Downloads/courier_canary/artifacts/canary_A.txt
SHA256_EXPECTED=96c1471cc2dfc55d49de5a3279dc927774a84b0f5c5bdc7c5755f19d8de9391c
PHYSICAL_HASH=96c1471cc2dfc55d49de5a3279dc927774a84b0f5c5bdc7c5755f19d8de9391c  ✓ MATCH

## Prior Canonical "CANARY_OK\n" Fixture (hermetic isolation proof)
CONTENT_BYTES=CANARY_OK\n  (10 bytes)
SHA256=575114332fb4ccd482dd9ca60dbaccc15b579afeb372f0c92b6f7eefe219049b
USED_IN=prior Canary isolation proof run (confirmed RECONCILED)

## Verifier Behavior with Correct expected_sha256
result artifact: {path: "canary_A.txt", sha256: "96c1471...", expected_sha256: "96c1471..."}
server fetches bytes, computes SHA-256, compares → MATCH → PASS

PROVEN=Correct fixture physically computed and verified.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_22
