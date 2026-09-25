# CODEX: Muse Wall SlotLock never reclaims a dead holder

Scope: `scripts/windows_muse_wall/slot_state.py` (`SlotLock`), its callers in
`scripts/windows_muse_wall/supervisor.py`. Do not touch P3 files.

## Defect

`SlotLock.__enter__` uses `O_CREAT | O_EXCL` and writes `"<pid> <time>"`. If the supervisor
dies inside a `with SlotLock(...)` block (hard kill, power loss), `__exit__` never runs and
`slot.lock` stays. Every later `reconcile_slot`, `start_slot` and `stop_slot` on that slot then
raises `RuntimeError: slot lock already held` forever. The slot cannot be repaired without
deleting files by hand.

## Reproduction (verified 2026-09-25 on Windows, .venv Python 3.14)

```python
import tempfile, pathlib
from scripts.windows_muse_wall.supervisor import MuseWallSupervisor
root = pathlib.Path(tempfile.mkdtemp())
sup = MuseWallSupervisor(root, {"desired_slots": 1}); sup.initialize()
(sup.slot_dir("MUSE-01") / "slot.lock").write_text("999999 1.0")
sup.reconcile_slot("MUSE-01")   # RuntimeError: slot lock already held
```

## Expected

A lock whose holder is provably dead is reclaimed. A lock held by a live process is still
refused. Use pid plus process create_time (`process_matches`) as in commit 091d3288
(worker locks) and `scripts/provider_hub/hub.py:DispatcherLock`. Record `create_time` in the
lock file. Never delete a lock whose holder matches. A corrupt lock file fails closed.

## Proof required

A RED test with a dead-holder lock, then GREEN. A live-holder lock is still refused. A PID-reuse
case (same pid, different create_time) is reclaimed. `tests/test_windows_muse_wall.py` and
`tests/test_muse_wall_gaps.py` stay green.
