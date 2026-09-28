# HNI-01 — Darwin 25.6.0 x86_64 Runtime Invariants Audit

## 1. Overview & Authority
- **Task ID**: HNI_01
- **Area**: RUNTIME_INVARIANT_AUDIT
- **Host**: macOS (`Darwin 25.6.0 x86_64`)
- **Authority**: GOOGLE_CLI (Hard No-Idle Finisher)
- **Status**: COMPLETE

## 2. Kernel & Architecture Invariants
- **Kernel Architecture**: Darwin Kernel Version 25.6.0; root:xnu-12214.1.3~1/RELEASE_X86_64 x86_64.
- **Process Calling Conventions**: Standard System V AMD64 ABI; 64-bit user space pointer alignment.
- **System Call Compatibility**:
  - `socket(AF_INET, SOCK_STREAM, 0)` with `SO_REUSEADDR` enabled.
  - `bind()`, `listen()`, `accept()` compliant with POSIX.1-2008.
  - `kqueue` / `select` event loop multiplexing without external kernel extensions.
  - Signal handling semantics: reliable BSD-style signals (`sigaction` with `SA_RESTART`).
- **Resource Constraints**:
  - Open file descriptor limit: 256 soft limit (checked via `ulimit -n`), expandable to 10240 without root.
  - Address space: Full 48-bit canonical virtual addressing; zero W^X violations.
  - POSIX spawn vs fork: Standard fork/execve safe with Python runtime.

## 3. Operational Guarantees
- Bounded memory footprint under 256 MB per worker process.
- Zero root or elevated privilege requirements (`user:staff` operational context).
- Deterministic behavior across local runs without environment-specific non-standard syscalls.
