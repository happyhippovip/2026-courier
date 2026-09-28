# Family 11: Cross-Host Portability Audit (Mac vs Windows)

**Status**: AUDITED  
**Hosts**: Mac (`Darwin x86_64`) / Windows (`win32 / PowerShell`)

---

## 1. Cross-Platform Architectural Matrix

| Dimension | Mac Host (`Darwin`) | Windows Host (`win32`) | Portability Contract / Invariant |
|---|---|---|---|
| **Path Handling** | POSIX forward slash (`/`) | Backslash (`\`) or `PureWindowsPath` | `PureWindowsPath` enforced in `integration_contract.py:167`; prevents backslash escape vulnerabilities. |
| **Path Traversal Guard**| Rejects `..` in POSIX parts | Rejects drive letters (`C:`) and `..` | Explicitly validated in contract validation (`drive or root or ".." in parts`). |
| **Temporary Dirs** | `/tmp` or `tempfile.TemporaryDirectory` | `%TEMP%` / `AppData\Local\Temp` | Python standard library `tempfile` abstraction used across tests. |
| **File Locking** | `fcntl.flock` (advisory POSIX lock) | Named mutex / `msvcrt.locking` | Mac daemon uses `fcntl`; Windows daemon uses PowerShell mutex locking (`candidate-b-1` fix). |
| **Process Identity** | POSIX PID (`os.getpid()`) | Windows PID (`System.Diagnostics.Process`) | Verified in `run_id` format (`pid-{PID}`). |
| **Process Termination** | `SIGTERM` / `SIGKILL` | `taskkill /F /PID` or `Stop-Process` | Both hosts persist state before shutdown; `PHYS-003` proven on Mac. |
| **Line Endings** | LF (`\n`) | CRLF (`\r\n`) | Verifier tests normalize artifact bytes as raw octet streams (`application/octet-stream`). |
| **Encoding** | UTF-8 native | Windows-1252 / UTF-8 | PowerShell daemon encoding explicitly bound to UTF-8 in `4c1e24cc`. |
| **Port Isolation** | Default `8080`, Canary on `8081` | Default `8080`, isolated ports via env | `COURIER_SERVER` environment variable controls port binding. |

---

## 2. Portability Findings
- **Windows Verification Requirement**: Mac cannot execute Windows-only binary or PowerShell-specific locking tests natively (`WINDOWS_REQUIRED` for Windows daemon live test).
- **Contract Equivalence**: Invariant contracts in `scripts/integration_contract.py` are pure Python and verified identical across both platforms.
