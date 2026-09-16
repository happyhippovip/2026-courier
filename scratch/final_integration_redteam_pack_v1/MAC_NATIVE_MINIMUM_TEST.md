# MAC-NATIVE MINIMUM TEST SPECIFICATION

- **Mission**: `WINDOWS_FINAL_INTEGRATION_REDTEAM_PACK_V1`
- **Target OS**: macOS / Darwin (Physical Apple Silicon or Intel Mac Host)
- **Scope**: Irreducible test to validate `proc_pidinfo` process start-time retrieval under real Darwin permissions, App Sandbox, and System Integrity Protection (SIP).
- **Execution Condition**: Strictly POST-FREEZE, after the active Mac Courier lifecycle is frozen and sealed.

---

## 1. WHY THIS TEST CANNOT BE RUN ON WINDOWS
Windows provides `GetProcessTimes()` via Win32, which is fully proven. However, macOS uses either:
1. `proc_pidinfo(pid, PROC_PIDTASKINFO, 0, &taskinfo, sizeof(taskinfo))` via `libproc`
2. `sysctl(KERN_PROC_PID)` via `libc`

Whether non-root processes in the active agent runtime environment have permission to query `proc_pidinfo` across process boundaries without triggering `EPERM` under macOS sandbox profiles is an OS-kernel-specific question that can only be proven on Darwin.

---

## 2. THE MINIMAL IRREDUCIBLE TEST SCRIPT (`mac_proc_pidinfo_probe.c`)
This minimal test requires zero external dependencies and compiles with standard `clang`:

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <sys/types.h>
#include <libproc.h>

int main(int argc, char *argv[]) {
    pid_t target_pid = (argc > 1) ? atoi(argv[1]) : getpid();
    struct proc_taskinfo taskinfo;
    
    printf("=== MAC DARWIN PROC_PIDINFO MINIMAL TEST ===\n");
    printf("Probing PID: %d\n", target_pid);

    int ret = proc_pidinfo(target_pid, PROC_PIDTASKINFO, 0, &taskinfo, sizeof(taskinfo));
    if (ret <= 0) {
        printf("RESULT: ERROR (errno=%d: %s)\n", errno, strerror(errno));
        if (errno == EPERM) {
            printf("CONCLUSION: EPERM_SANDBOX_RESTRICTION -> Fallback to UNKNOWN required.\n");
        } else if (errno == ESRCH) {
            printf("CONCLUSION: PROCESS_NOT_FOUND -> Definite mismatch.\n");
        }
        return 1;
    }

    printf("RESULT: SUCCESS\n");
    printf("Start Time: %llu sec, %llu microsec\n", 
           (unsigned long long)taskinfo.pti_start_tvsec, 
           (unsigned long long)taskinfo.pti_start_tvusec);
    printf("CONCLUSION: Darwin kernel process start-time resolution is reliable.\n");
    return 0;
}
```

---

## 3. FOUR IRREDUCIBLE ADVERSARIAL QUESTIONS TESTED

| Test Case | Scenario | Expected Darwin Behavior | Required Safe Courier Fallback |
|---|---|---|---|
| **TEST-MAC-01** | Self & Child Process Inspection (`target_pid = child`) | `proc_pidinfo` returns `SUCCESS` with positive start timestamp. | Use `start_time` in multi-factor tuple. |
| **TEST-MAC-02** | Cross-Process Inspection (`target_pid = other non-root process`) | Returns `SUCCESS` if same UID; returns `EPERM` if sandboxed. | If `EPERM`, return `UNKNOWN`; **NEVER KILL**. |
| **TEST-MAC-03** | Disappearing Process (Race Condition / TOCTOU) | Process exits between PID check and `proc_pidinfo` -> returns `ESRCH`. | Return `DEFINITE_MISMATCH`; clean up lease. |
| **TEST-MAC-04** | Rapid PID Recycling Simulation | Worker child exits; spawn 10,000 short-lived processes until PID wraps; inspect new PID. | `pti_start_tvsec` of new process > old lease timestamp; flags `PROCESS_RECYCLED`. |

---

## 4. ACCEPTANCE CRITERIA
- If all 4 pass: B01 integrates with high-resolution Darwin process tracking.
- If TEST-MAC-02 returns `EPERM`: Courier implements `UNKNOWN` fallback (treats uninspectable processes as `UNKNOWN`, disabling blind kill while supervising via file deliverables).
- **Duration of Test**: < 5 seconds.
