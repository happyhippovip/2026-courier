# MAC-FINISH-21 — Pilot Onboarding Packet

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-21
- **Area**: PILOT_ONBOARDING_PACKET
- **Status**: COMPLETE

Gated preparation for pilot onboarding. Adheres strictly to the law that physical pilot onboarding occurs ONLY after Core Freeze declaration.

---

## 2. Onboarding Gate Prerequisites
1. `CORE_FREEZE_DECLARED = YES`
2. Sandboxed test user space provisioned.
3. Explicit user consent recorded in audit ledger.

---

## 3. Onboarding Protocol
- Sandbox isolation: User jobs execute in ephemeral virtualized containers.
- Resource fences: CPU capped at 2 cores; memory capped at 2 GB per user job.
