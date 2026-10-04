# M224: Runner Dependency Completeness

## Goal
Prove that the native runner guarantees execution isolation by minimizing dependencies on the host operating system.

## Implementation & Proof
1. **Self-Contained Execution**:
   - `daemon.py` invokes instructions strictly via built-in system shells (`powershell.exe` for Windows). 
   - It requires NO third-party Python modules (like `requests` on older versions, replaced by standard library `urllib`).
2. **Base64 Instruction Encoding**:
   - `daemon.py` encodes its instruction into UTF-16LE Base64 for `powershell -EncodedCommand`.
   - This isolates Courier from parsing issues, quotation bugs, and shell injection vulnerabilities related to complex multi-line command payloads.

## Conclusion
Courier's native runner preserves perfect dependency hygiene by utilizing strict standard libraries and Base64-encoded shell invocation.
