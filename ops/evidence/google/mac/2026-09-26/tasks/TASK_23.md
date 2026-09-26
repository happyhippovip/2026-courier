# TASK_23 — Newline-Variance Fixture

STATUS=DONE (source-audited + hash-computed)

## Newline Variants and SHA-256
| Content          | Bytes                      | SHA-256                                                          | Verdict |
|------------------|----------------------------|------------------------------------------------------------------|---------|
| CANARY_OK\n (LF) | 43 41 4e 41 52 59 5f 4f 4b 0a | c0bb504d8c6cb7280ab683bb08cdba16724567270d8f614bf62992b3c9083e0f | Reference|
| CANARY_OK\r\n    | ... 0d 0a                  | 186dc20ecb436c019ba88e9fcdd76694ac537d083a1204fcafb86ff4dc26fb53 | FAIL (≠) |
| CANARY_OK (no NL)| no trailing byte           | b0f59d403979fee931a778bd0a6ea20133c538f642e9dc508cf136b5a34a1027 | FAIL (≠) |
| COURIER-A2B-A\n  | 43 4f 55 52 49 45 52 2d 41 32 42 2d 41 0a | 96c1471cc2dfc55d49de5a3279dc927774a84b0f5c5bdc7c5755f19d8de9391c | Canary A |

## Key Point
SHA-256 is byte-exact. CRLF vs LF produces different hashes → FAIL.
Workers on Windows must normalize to LF before upload, or expected_sha256 must be computed from CRLF bytes.
For Canary 1, artifact is written by Mac shell script → LF guaranteed.

PROVEN=Newline variance hashes physically computed. Byte-exact verification confirmed.
UNKNOWN=None
BLOCKER=None (Canary 1 uses Mac-generated artifact with LF)
NEXT=TASK_24
