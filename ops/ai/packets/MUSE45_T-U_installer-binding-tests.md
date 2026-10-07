# MUSE-45 T-U — Installer/binding test sweep (read-only, close-out)

Branch fix-cb1-new @ 329abd80. Static only. No edits but this packet.
Closes the test-pin picture for both daemons (companion to T-P/T-S).

## Windows binding: delivery semantics PINNED (7 tests)

tests/test_windows_worker_binding.py pins exactly the T-Q strengths:
same-result resend without re-execution, transient-retry-identical-payload,
undelivered-blocks-new-claims, terminal-4xx-not-retried + evidence kept,
started-released-not-reexecuted (parametrized phases), missing-artifact->
FAILED (not contract violation), binding accepted by server contract.
No test touches the bootstrap log-handshake: Q9 UNPINNED, reconfirmed.

## Windows credentials: precedence + no-leak PINNED (7 tests)

tests/test_windows_worker_credentials.py: no-hardcoded-key-in-source,
env-over-config precedence, missing-key fail-closed without network,
nonzero-exit + never-prints-key, no-leak on register failure, bootstrap-
config fallback, env-wins + "local"-placeholder ignored.
Q1 refinement: suite pins "never prints/leaks key" (transport/log hygiene)
while ACKNOWLEDGING config.json as key store — plaintext-AT-REST stays
unflagged by design. Note stands as designed debt, not oversight.

## Mac install: installer path PINNED (2 tests)

tests/test_mac_worker_install.py: install.sh resolves repo root from any cwd
+ plist content pins; setup_keychain.sh hides API-key input. No mac-side
bootstrap-handshake test needed (launchd mechanism differs; Q9 is win-only).

## Verdict

Both daemons' safety/delivery/credential BEHAVIORS are test-pinned; my open
items are precisely the UNPINNED remainder: O4 (echo sink), Q9 (handshake),
M1/M3 (spawn quoting/CLI args), O1-O3/O5-O8 (nits). Failing-first regression
tests for O4+Q9 remain the natural shell-back work. Worker-path audit on
fix-cb1-new is now COMPLETE (code + tests + contracts, both platforms).
