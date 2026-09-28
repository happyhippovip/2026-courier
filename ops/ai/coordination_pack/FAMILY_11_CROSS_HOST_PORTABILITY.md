# Family 11: Cross-Host Portability Audit (Mac vs Windows)

Status: AUDITED
Scope: Invariant preservation across POSIX (Darwin) and Windows NT.

---

## 1. Portability Matrix

| Subsystem | Mac (Darwin POSIX) | Windows NT | Unified Invariant / Guard |
|---|---|---|---|
| **Path Handling** | Forward slashes (`/`), case-sensitive or insensitive (APFS) | Backslashes (`\`), drive letters (`C:\`), case-insensitive | Use `pathlib.Path` exclusively; serialize relative POSIX paths in contracts. |
| **Temporary Dirs** | `/tmp` or `/var/folders/...` | `C:\Users\...\AppData\Local\Temp` | Use `tempfile.TemporaryDirectory()`; never hardcode `/tmp`. |
| **File Locking** | `fcntl.flock()` | `msvcrt.locking()` or atomic directory creation | Abstract via `runtime_state.control_lock` with platform-adaptive fallback. |
| **Process Identity** | PID, `kill -0`, POSIX process groups | PID, `tasklist`, job objects | Record `process_identity(pid, start_time)` to avoid PID reuse confusion. |
| **Process Signals** | `SIGTERM`, `SIGINT`, `SIGKILL` | `CTRL_C_EVENT`, `TerminateProcess()` | Graceful shutdown catches `KeyboardInterrupt` and `SIGTERM`. |
| **Line Endings** | `\n` (LF) | `\r\n` (CRLF) | Open text files with `newline=""` or explicit `utf-8`; git `.gitattributes` text=auto. |
| **File Encoding** | UTF-8 default | UTF-8 / Windows-1252 / CP1252 | Strict `encoding="utf-8"` on all open/json calls. |
| **Credentials** | macOS Keychain or environment variables | Windows Credential Manager or environment | Separate worker/verifier keys via environment variables; zero hardcoding. |
| **Port Isolation** | `PORT=8080`, `PORT=8081` | `PORT=8080`, `PORT=8081` | Dynamic port binding via environment variable `PORT`. |
| **Runtime Fingerprints** | Darwin kernel version, SHA of Python | Windows build, PowerShell version | Fingerprint recorded in execution evidence metadata. |

---

## 2. Windows Verification Gate
- Mac host cannot directly execute Windows PowerShell scripts.
- **WINDOWS_REQUIRED**: Execution of `tests/test_windows_worker_contract.py` and `scripts/windows_worker/daemon.py` must run on Windows Central Worker.
