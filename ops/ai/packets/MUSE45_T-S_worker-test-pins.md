# MUSE-45 T-S — Worker-test pin check for Q-/O-findings (read-only)

Branch fix-cb1-new @ 329abd80. Checked the 6 worker-contract test files for
pins on my Q1/Q9/O4 findings. Static only. No edits.

## Verdicts (OBSERVED)

- Q9 (bootstrap handshake broken): UNPINNED. No test in the 6 files references
  "Registered successfully" or the bootstrap log-handshake. The 30s-timeout-
  always path has zero coverage; a regression test would need a live-ish boot
  (shell session). Stands open.
- Q1 (plaintext API key in config.json): test-ACKNOWLEDGED as the model, not
  flagged. tests/test_windows_worker_credentials.py pins precedence (env >
  config) + fail-closed-no-network, with an inline comment "config.json may be
  read (bootstrap.ps1 stores the key there)". The suite blesses the shape; my
  note (misleading "stored securely" message, no ACL) stands as design debt.
- O4 (NATIVE echo shell sink): UNPINNED. "echo hi" in test_mac_worker_recovery
  is a fixture string for MOCKED run_native, never executed. Combined with T-P:
  no test anywhere executes the real echo path with a smuggling tail.
- test_windows_worker_binding.py + test_windows_worker_contract.py: checked,
  no pins on Q/O items (negative result recorded to close the sweep).

## Note

Pinning Q9/O4 as failing-first regression tests is the natural shell-back
work (both need live execution). Not writable from here (no runner + foreign
test scope). Handed to owner via this packet.
