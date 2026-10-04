Evidence for Source-State-Truth:
- Bug in server/app.py: WORKER_RESTARTED_AND_LOST_STATE set status to PENDING, making it unclaimable.
- Fixed: Set to QUEUED.
