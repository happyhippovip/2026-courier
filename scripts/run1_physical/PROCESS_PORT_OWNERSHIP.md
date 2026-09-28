# PROCESS PORT OWNERSHIP & PROTECTION

## Requirements
To ensure isolation during RUN 1 and RUN 2 on the Mac host, physical runs must strictly own their process group and ports, and refuse to boot if foreign processes are detected on required resources.

## Pre-Flight Check
1. Target port (e.g., `8080` if web, or `0` for dynamic binding) must be free.
2. If another instance of the courier run logic is already active in the process tree, the boot script must `exit 1` instantly to prevent cross-contamination.

## Verification
```bash
# Verify no leaked processes from same candidate
if pgrep -f "run_physical.py --sha {{FINAL_SHA}}"; then
   echo "CRITICAL: Foreign process detected holding this SHA's execution context. Aborting."
   exit 1
fi
```
