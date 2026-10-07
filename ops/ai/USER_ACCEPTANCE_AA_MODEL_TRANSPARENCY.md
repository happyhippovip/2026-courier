# User Acceptance: Model & Provider Transparency

**User Problem:** Which AI model is currently executing my task, and is it hallucinating or actually reading my files?
**Current Runtime Truth:** The execution runs via `gemini_worker_adapter.py` / `mac_worker_adapter.py`. The model variant and provider are defined in the runtime binding, but not overtly exposed to the end-user during a run.
**Acceptance Requirement:** The user must be able to view a "Provider & Model" tag on the running task, guaranteeing which system is currently billed and executing.
**Missing System Support:** Needs a local dashboard or CLI flag (`courier status --provider`) that reads the currently bound execution model without interrupting it.
**Preparable Now:** Yes, the tracking document and CLI command specification can be drafted.
**Blocked Until:** Product Shell Gate opening.
