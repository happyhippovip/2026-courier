# BUGFIX EVIDENCE

## OUR_REPO_BUG 2: Courier Verifier Fails on List of Target Capabilities
**Symptom**: `courier_verifier.py` uses `str(task.get("target_capability")).lower()` and expects `"linux", "windows", "mac", "github"`. If a task contains multiple targets in a list (e.g. `["python", "windows"]`), `str()` turns it into `"['python', 'windows']"`, failing the strict inclusion check with `Malformed or ambiguous target`. This breaks Result Reuse and NEXT_READY loop.
**Fix**: Updated `courier_verifier.py` (lines 65-68, 94-99) to detect if `raw_target` is a list, cast elements to lowercase string, and check `if not any(k in target for k in known_targets)`. Added `antigravity` to `known_targets` since `app.py` accepts it. Also updated GitHub check to use `"github" in target`.
**Status**: Repaired locally in `courier_verifier.py`.

## OUR_REPO_BUG 3: Result Reuse `ACK_DUPLICATE` Fails with 409 Conflict
**Symptom**: In `server/app.py` line 363, duplicate result checks crash when one artifact list is missing (`None`) and the other is empty (`[]`). This evaluated to `False`, forcing the logic into conflict resolution (`409 Conflicting result for already processed task`), destroying idempotency.
**Fix**: Standardized `arts` array to `[]` when falsy within `sort_artifacts(arts)` lambda wrapper inside `app.py` for `/tasks/result` and `/tasks/verify`.
**Status**: Repaired locally in `server/app.py`.

With these and the `HUMAN_REQUIRED` state bug in `server/app.py`, we have completed the **3 required real OUR_REPO_BUG** bugfixes for the NEXT_READY / Motor prep paths. All tasks were solved deterministically with targeted patches.
