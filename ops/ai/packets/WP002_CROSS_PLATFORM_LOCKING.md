# WP002: Cross-Platform File Locking in tests

## Target
`scripts/local_swarm_claim.py` (and any associated lock test)
`tests/test_m201_process_identity.py` (if it directly imports `fcntl`)

## Defect
Currently, the codebase relies on `fcntl` for file locking in the claim scripts. `fcntl` is a Unix-only module and causes `ImportError` on Windows (`MUSE_WINDOWS` workers). This natively breaks execution of local claim logic or test collection on Windows machines.

## Instructions for SOLE_WINDOWS_WRITER
1. Introduce a cross-platform locking wrapper or conditional imports:
   ```python
   import os
   if os.name == 'nt':
       import msvcrt
       # implement lock via msvcrt.locking
   else:
       import fcntl
       # implement lock via fcntl.flock
   ```
2. Apply this fix to `scripts/local_swarm_claim.py` and update tests to mock or conditionally execute lock-dependent logic based on the platform.
3. Verify that `pytest tests/` successfully collects and executes on a Windows node without `ImportError: No module named 'fcntl'`.

## Causal Path
The system was originally designed with Unix execution environments in mind (Mac/Linux). As Courier scales to include `MUSE_WINDOWS`, OS-specific dependencies like `fcntl` must be gracefully handled or shimmed.
