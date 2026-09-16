# MAC NATIVE PROOF QUEUE — FORMAL SPECIFICATION

The following invariants cannot be decisively proven on Windows host environments and are safely deferred to the native macOS Courier test harness:

1. **APFS Copy-on-Write Atomic Swap Invariant**
   - *Target*: macOS APFS atomic clone semantics (`clonefile`) during workspace snapshotting.
   - *Harness*: `tests/mac_native/test_apfs_atomic_swap.sh`
   - *Verification Criteria*: Zero byte corruption during simulated kernel panic midway through `clonefile()`.

2. **launchd Service Supervision & Respawn Semantics**
   - *Target*: macOS `launchd` daemon plist supervision lifecycle.
   - *Harness*: `tests/mac_native/test_launchd_respawn.sh`
   - *Verification Criteria*: Immediate worker respawn with fresh process lease; no zombie PID recycling.

3. **macOS Thermal State Notification Framework**
   - *Target*: `NSProcessInfoThermalStateDidChangeNotification` integration.
   - *Harness*: `tests/mac_native/test_thermal_throttling.sh`
   - *Verification Criteria*: `THERMAL_PRESSURE` event triggers local load shedding without sending cross-machine throttle signals to Windows workers.

4. **macOS Keychain Security Enclave Access**
   - *Target*: Apple Keychain access control list (ACL) enforcement.
   - *Harness*: `tests/mac_native/test_keychain_acl.sh`
   - *Verification Criteria*: Non-privileged subagent read attempt fails closed with `errSecAuthFailed`.
