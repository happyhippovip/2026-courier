# Pilot Metrics & Goal Contract

## Minimum-Real-Pilot Goal Contract (GQ45)
- **Goal:** Execute a multi-turn, actual useful task (e.g., repository analysis, simple file rewrite) across the entire Courier chain.
- **Criteria for Success:** Task completes without human intervention beyond the initial command. Output artifact matches expected goal structure.

## Pilot Metrics (GQ46)
- **Setup Time:** Time from `git clone` to system ready.
- **HIPG (Human Interventions per Goal):** Number of times a human had to correct or unblock. Target: 0.
- **RSR (Run Success Rate):** Percentage of dispatched tasks successfully reconciled.
- **NDR (No Duplicate Rate):** Percentage of tasks dispatched exactly once.
- **Provider Cost Class:** Overall cost profile (low, medium, high).
- **Time to Useful Result:** Total wall-clock time from `goal` submission to verified output.

## Pilot-Value-Signal (GQ47)
- **Positive:** Output artifact is verified correct; zero human interventions.
- **Negative:** System hangs, loops, duplicates tasks, or requires manual state editing.
- **Unclear:** Output completes but is technically incorrect due to provider hallucination, not Courier machinery.

## Product-Shell-Gate (GQ48)
- Gateway to transition from raw scripts to a packaged product shell (e.g., DMG/EXE).
- **Condition:** MUST NOT be unlocked until Pilot-Value-Signal is Positive.

## Task/Result Identity (GQ43)
- Identity is established entirely by `task_id`, `goal_id`, `attempt_id`, and `dispatch_id`. The specific provider (Google, Muse, Sonnet, Opus, Codex) is recorded only in the `worker_id` and `target_capability` fields.

## Provider-Ausfälle Isolieren (GQ44)
- Provider timeouts are treated as `FAILED_VERIFICATION` or just discarded by the `dispatch_id` timeout in the server. A broken provider will simply fail to heartbeat or submit results, allowing the server to reassign the task to another healthy provider of matching capabilities.
