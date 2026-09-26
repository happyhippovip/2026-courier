# Courier Wall Visual / Icon Language

Status: UI/ops design requirement.  
Purpose: make a large wall understandable at a glance without sacrificing textual truth.

## Core icons

🎯 GOAL — requested outcome  
📜 LEDGER — durable truth / history  
🧠 PLAN — coordinator/decision logic  
🚀 READY / DISPATCH — legal next work / dispatched  
👀 READ ONLY — cannot mutate source  
✍️ WRITER — owns a mutable source scope  
🧪 VERIFY — evidence being checked  
✅ VERIFIED / DONE — accepted according to the stated proof surface  
🟡 WAITING — dependency/provider/time wait  
🛡 GUARDED — deliberately withheld by safety/resource/cost guard  
💤 IDLE — no current useful READY work  
🔁 RESTART / RECOVERY — resuming durable work  
🔥 RESOURCE PRESSURE — thermal/CPU/RAM pressure  
💸 BUDGET / QUOTA — spend or provider-capacity concern  
🧩 DEPENDENCY — blocked by another task/result  
🍎 MAC — Mac host  
🪟 WINDOWS — Windows host  
🟨 GOOGLE — Google/Antigravity lane  
🟣 MUSE — Muse lane  
🧠 CODEX — independent code review  
🧿 OPUS — convergence/product judge  
🌍 WORLD — larger long-term Courier work world

## Truth rule

Icons are a second visual channel only.

Every icon must have text/state beside it.

Do not use a happy/success icon for:
- RESULT_RECEIVED
- SELF_REPORTED
- UNKNOWN
- partially covered proof
- stale evidence

Contradictory state should render as UNKNOWN/CONTRADICTED, never silently green.

## Wall card example

🌍 COURIER WALL
Requested 10
Admitted 8
Active 6
Waiting 2
Guarded 2
Heavy 1/1

🍎 M01  👀  RESTART_DURABILITY      🧪 VERIFY
🍎 M02  👀  AUTO_B_DISPATCH         ✅ PARKABLE
🪟 W01  ✍️  FINAL_CANDIDATE         🚀 ACTIVE
🟨 G03  👀  TEST_EVIDENCE           🟡 WAITING
🟣 M05  👀  ARTIFACT_TRUTH          ✅ PARKABLE
🛡 W09       RESOURCE_GUARD          🔥 THERMAL

## Human-facing principle

The user should be able to answer in seconds:

- What did I ask for?
- What is working?
- What is really verified?
- What is waiting?
- Does anything need me?
- How much capacity is free?
- Why is a requested slot not active?
- What happens next?

## Accessibility

Do not rely on color alone.
Do not rely on emoji alone.
Use short plain labels alongside icons.
