# Opus 4.6 Windows 100-Task Queue Usage

This queue contains 100 logical tasks.

Recommended simultaneous Opus windows:
- 4 = preferred
- 6 = good
- 8 = upper normal
- 10 only if at least 10 independent READY O48 tasks remain
- 100 simultaneous Opus windows = NOT RECOMMENDED

Reason:
The queue is deep so free windows always have distinct work, but Opus remains an expensive C4 model.
Use Google/Muse/local tools for deterministic/bulk checks.

Prompt:
ops/ai/OPUS46_WINDOWS_QUEUE_100_WORKER_PROMPT.txt
