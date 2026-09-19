# COURIER — RELEASE ACCEPTANCE PACKET

## IDENTITY
- **Commit SHA**: 47cfbbe89cc00b6f00a5db55cea64fb265b2438b (Mac)
- **Tree SHA**: d6cba0889f5e049b0ac517ad1b1acf5364128988
- **Loaded Runtime Identity**: FAILED (Git HEAD used instead of memory)

## CORE
- durable queue: YES
- task/attempt/execution/result binding: YES
- reconciliation: YES
- recovery: YES
- idempotency: YES

## CANNON
- NORMAL max1: VERIFIED
- FAST max2: VERIFIED (Physical proof complete)
- TURBO: LOCKED

## SCOPES
- one writer: FAILED (APFS case-insensitive / symlinks bypass locks)
- fencing: YES
- stale writer rejection: YES

## SCALE
- 10k/100k/1M: FAILED (Lock contention on prefetch SQLite upgrade)

## NIGHT
- bounded authorization: FAILED (Budget limit not strictly enforced)
- human gates: YES
- no polling: YES

## CROSS PLATFORM
- Windows: 806562788f99b966d3da28619aefe9ab03248540
- Mac Test Build: 47cfbbe89cc00b6f00a5db55cea64fb265b2438b
- Exact candidate identity: FAILED (Mismatch)

## FALSE GREEN
- No fake acceptance: FAILED (Git HEAD usage)

---

RELEASE_PACKET_STATUS=FAIL
FIRST_DEFECT=Cross Platform Identity Mismatch (Windows Candidate 80656278 != Mac Candidate 47cfbbe8)
