# MAC-FINISH-18 — Core Freeze Closeout Packet

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-18
- **Area**: CORE_FREEZE_CLOSEOUT_PACKET
- **Status**: COMPLETE

Defines the formal Core Freeze declaration criteria, Git tagging protocol, and codebase lock rules.

---

## 2. Prerequisite Gates
Core Freeze CANNOT be declared until:
1. Candidate SHA verified against canonical remote.
2. 44 targeted tests PASS (`SKIPPED=0`).
3. 12-case matrix PASS.
4. RUN_1 passes with zero human relays.
5. RUN_2 passes with zero Task A replay.
6. Proof Card fully attested and cryptographically anchored in ledger.

---

## 3. Freeze Actions
```bash
# Tag the frozen core commit
git tag -a core-freeze-v1.0 -m "Courier Core Freeze v1.0 - All Physical Proofs Verified"
```
All modifications to `server/`, `scripts/`, `dashboard/` are permanently locked until commercial pilot completion.
