# Window Capacity Profiles

Courier Symphony exposes persistent reviewer/UI capacity profiles: **8, 12, 16, 32**.

The selected profile is stored locally in `events/runtime-state/window_capacity_state.json`, so it survives application and machine restarts on the same installation. Git tracks the policy/defaults and implementation, not each operator toggle.

Scaling down is **drain-only**: existing work is not killed. New window/session admissions stop until active count is at or below the selected target.

Safety invariants are independent of the UI slot budget:
- mutable writers: **1**
- heavy jobs per host: **1**

The dashboard control can be hidden; the compact footer **⚙ Capacity** button restores it.

CLI:
```bash
python scripts/window_capacity_policy.py show
python scripts/window_capacity_policy.py set --slots 32
python scripts/window_capacity_policy.py set --slots 16
python scripts/window_capacity_policy.py set --slots 8
python scripts/window_capacity_policy.py set --pause
python scripts/window_capacity_policy.py set --resume
python scripts/window_capacity_policy.py set --hide
python scripts/window_capacity_policy.py set --show-controls
```
