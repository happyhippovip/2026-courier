# Courier: 90-Second Demo Recording Package

This document contains everything needed to record a professional, accurate demonstration of Courier's core orchestration capabilities.

## Pre-Recording Checklist
- [ ] Terminal window is clean (e.g., `clear` run).
- [ ] No existing Courier servers are running on port 8080 (`lsof -i :8080`).
- [ ] No `demo_state.json` exists in `server/state/` (handled automatically by script, but good to verify).
- [ ] Text size is increased for visibility on mobile/desktop screens.
- [ ] Audio recording equipment is tested.
- [ ] Screen recording software is set to capture only the terminal window (no personal desktop icons).

## Exact Terminal Command
```bash
# From the root of the 2026-courier repository
python3 demo/local_demo.py
```

## Expected Sequence & Narration

**Target Duration:** 60 - 90 seconds
**Visual:** Single terminal window.

**[0:00 - 0:15] The Problem & Introduction**
*Action: Type `python3 demo/local_demo.py` but do not press enter.*
**Narrator:** "Today's AI agents are fragile. If your browser closes, a provider hits a rate limit, or a script crashes, the entire context is lost. Courier fixes this by separating the interactive agent from the execution runtime. Let's see how."

**[0:15 - 0:30] Submitting the Goal**
*Action: Press Enter. The BOOTSTRAPPING and GOAL RECEIVED steps appear.*
**Narrator:** "We start the Courier Motor and submit a multi-step Market Research Goal. The Motor immediately writes this goal to its durable state. From here on out, Courier owns the execution."

**[0:30 - 0:45] Execution & The Crash**
*Action: Wait for 'Worker A finished data extraction' and the red 'SIMULATING CRASH' text to appear.*
**Narrator:** "Local Worker Process A spins up and begins extracting data. But in the real world, things fail. We simulate a catastrophic failure by explicitly force-killing Worker A mid-workflow."

**[0:45 - 1:05] Recovery & Replacement**
*Action: Wait for the yellow 'STATE PRESERVED' text and the cyan 'Starting Local Worker Process B' text.*
**Narrator:** "Without Courier, your work is gone and you're starting over. But Courier's Motor detects the crash, preserves the exact state, and safely suspends the task. A replacement worker—Process B—starts up, instantly picks up exactly where Worker A left off, and continues processing."

**[1:05 - 1:20] Verification & Completion**
*Action: Wait for the green 'VERIFIED RESULT' and 'DONE' text.*
**Narrator:** "Worker B completes the final reporting steps. An independent verifier process automatically checks the result. The goal is marked DONE—with zero human intervention or 'continue' prompts required."

**[1:20 - 1:30] Outro / CTA**
*Action: Fade recording to black or display Courier URL.*
**Narrator:** "Courier is the durable runtime for work that outlives the AI session. Visit our website to request a pilot and bring durable execution to your workflows."

---

## Fallback Material (If Video is Unavailable)
If bandwidth or platform limitations prevent video playback, use the following text sequence:

1. **Screenshot 1 (The Goal):** Capture the terminal showing `Goal assigned ID: goal-xyz`. Caption: *Courier Motor accepts the goal and writes it to durable state.*
2. **Screenshot 2 (The Crash):** Capture the red text showing `SIMULATING CRASH: Terminating Local Worker Process A...` followed by `STATE PRESERVED. Motor safely waits.` Caption: *When a worker fails, Courier preserves state without requiring human intervention.*
3. **Screenshot 3 (The Recovery):** Capture the green text showing `Worker B successfully picked up Task 2!` and `All tasks complete. Final result is verified.` Caption: *A replacement worker seamlessly resumes the task and finishes the job.*
