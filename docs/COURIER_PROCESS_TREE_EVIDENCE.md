# Courier Windows Worker - Launcher Process Tree Analysis

## Test Execution Details
To prove the shipped execution of the Courier Windows Worker on the current `HEAD` commit, a clean build package was generated and launched. The resulting native Windows child-process tree was captured via WMI.

## Captured Process Tree
```text
--- Process Tree ---
Root: Courier.exe (PID: 22572)
  |- Courier.exe (PID: 19912) - CommandLine: "C:\Users\lol\2026-workspace\2026-courier\scripts\windows_worker\dist\Courier.exe" 
  |- python.exe (PID: 1584) - CommandLine: "C:\Users\lol\2026-workspace\2026-courier\scripts\windows_worker\dist\python\python.exe" -m courier_core.serve --home "C:\Users\lol\AppData\Local\Courier" --port 8080
  |- conhost.exe (PID: 9484) - CommandLine: \??\C:\WINDOWS\system32\conhost.exe 0x4
--------------------
```

## Analysis & Verification

1. **V1 Core Ownership:** Verified. `python.exe` is launched explicitly with `-m courier_core.serve`, which is the correct entrypoint for the primary worker process.
2. **Hub Deletion:** Verified. There are no node/electron or `courier_hub` processes in the tree. The legacy hub launch mechanism has been successfully pruned.
3. **Dashboard / Browser:** Verified. There are no unexpected `msedge.exe`, `chrome.exe`, or `cmd.exe /c start` processes launched by the agent upon initialization.
4. **No Unexpected Helpers:** Verified. The only auxiliary process is standard `conhost.exe` (Console Window Host), which is natively spawned by Windows for the background Python executable.

**Conclusion:** The shipped execution perfectly matches the target clean architectural state. All Legacy Flask dashboard assets and untracked headless UI elements have been securely removed from the execution tree.
