# WORK SCRIPT — local acceptance checkpoint

Date: 2026-09-18. Repository base: `71b3dc06749b6b9d8ac62834813c8b71aa842249`.
Scope: new isolated `work-script/` only. Existing dirty/untracked work belongs to
other writers and was not edited, staged, committed or pushed for this task.

## User correction after local verification

The user clarified that WORK SCRIPT targets the separate Courier Symphony
application/package ONLY. Their working Mac CLI and Muse must remain untouched.
README.md now records this boundary. The earlier live-window integration handoff
below is historical and superseded: next integration must identify a separate
application-owned session, never attach to the user's working Mac CLI/Muse.
No controller, widget, prompt, runtime, settings or installed application changed
for this correction. No connection or activation was performed. The 21-test
result remains evidence for the unchanged controller, not live product delivery.
The fingerprints below record the original test snapshot; README.md subsequently
changed only to record this scope correction.

## Verified

- `node --test "work-script/*.test.mjs"`: 56 passed, 0 failed,
  0 skipped (21 controller + 3 transport + 13 exec-adapter + 6 slots + 7 admission + 3 context + 3 triage).
  Directory form `node --test work-script/` does not resolve on node v24;
  the glob form above is the evidence command.
- `node --check work-script/widget.mjs`: exit 0.
- Actual browser at a temporary loopback-only static preview: starts OFF;
  pressing WORK SCRIPT without an adapter displays
  `NICHT VERBUNDEN · Muse-CLI-Anbindung fehlt`, stays unchecked/OFF and reports
  no confirmed delivery. Visual layout inspected.
- A discovered stale-timer bug was repaired: explicit checks and OFF/ON cannot
  retain an earlier scheduled check. Dedicated regression passes.
- Tests use deterministic clocks and fake adapters, with no provider/model calls.
  They cover busy sessions, authorization, bounded checks, cross-tab exclusion,
  deduplication, restart default-OFF, ambiguous delivery, storage failures and
  stopping while a check is in flight. They are NOT Windows/CLI physical proof.

## Actual limits / next action

LIVE_MUSE_DELIVERY=NOT_CONNECTED
WINDOWS_END_TO_END=NOT_PROVEN
MODEL_CALLS_DURING_TESTS=0
PRODUCTION_FILES_CHANGED=NO
SECURITY_SETTINGS_CHANGED=NO

The current Muse bench appends a queue file; it does not prove input delivery to
an existing Muse CLI. The legacy runner starts another provider with a permission
bypass and was not used. The requested UI/CLI target URL and machine/session
remain unconfirmed. No active foreign scope was taken over.

Next action: identify that exact target and have the existing Muse/UI owner wire
the authenticated existing-session adapter specified in README.md. Verify real
delivery, atomic lease/session revalidation and canonical backend idempotency
before enabling the live control. Do not equate this preview with integration.

## SHA-256 fingerprints of tested files

```text
0ccc356bfae55b1b5190afde67712c44e285ebb6d306f73cf414ea8752bb3262  controller.mjs
8d3089dc66f528d4be27558ec291763a73df8fecaa3d94ae21c6d3c775a7dd24  controller.test.mjs (unchanged)
6d3150a39670a9b2b023a34cbcaacafa7dd3236ed30db69d43fa8fca1e7f9225  controller.transport.test.mjs
8f56462f629270d8d605e8e49a65c9eb3d3d9b096318552d03258d9a6cc485ca  exec-adapter.mjs
a7dc167e589f4cce85e0247a60a98c10308474c59a6182074ebac4862418bad1  exec-adapter.test.mjs
61fd993a72e466ba03844be234993b776e008e1b643ca7d200aff579d7e08229  stub-proc.mjs
91623ccbd3637801c9108995ef15a16294ca5cc94813e99277c4d02e242cd263  admission.mjs
8ad9de7b5e8066a87d96aae0b7a7afb84d2be923664492d532f848c95a2a82d3  admission.test.mjs
e720acb2c96c404a38088cb5948a2cd0a5c93577ae6caab8e8239a1cc366030b  admission100.fixture.json
cad490ca81dc1760b7ddb6ac9c8f0f26870aeb69df0434b0f0df5f93205f99a1  context-packager.mjs
07024c482efb01e1b15ac4f83fc5dc926aa4066d79c275010d31ac1bc40b114c  context-packager.test.mjs
54511b954d9678ea2bf446f7085943c42a07725d8348ed5839b74ccbb5c6e3c4  triage.mjs
69ed5be55c4c9e94efbfd46faff818f2fa83dfcfa092a79d1f23ce8ac73fdbf4  triage.test.mjs
32138bef2009b3bdc185457347b06f968817db670e98c81f0010337db5080835  evidence-map.fixture.json
1d8c751e768bdbca50682840f2c394aa3f30e8ad0f628478ef05eea7520d03ad  exec-adapter.mjs
2cab809c7dfb7d3c620809a254c4c5c3e959e53729dd74c64cbf1fd9dbda02e  exec-adapter.test.mjs
e8531eaacd14bb4ae4bea4613f178236076e532621cf5e3591b12d50aa971878  night-project.fixture.json
739ccd2d03d08002f3c980f7dca7961772b543d1c650ca02a6e17802175ca371  slots.mjs
5bceb33087954dd782428ed774ad9a5e8b7d117d3b8fce659a30e7e4432ad719  slots.test.mjs
267113c6035c090589c0e9454299ffcaedff42e46b3034b58439a3476f217faa  widget.mjs
93afef1aff063e47dd7eebdf6a60a4eac71c7a9bbc07efea0980dcd2393b71c8  prompt.mjs
48d93397ce861023f6813914b0771dd1c6e3f2936c1e5ed4cf976693944612c3  index.html
fc4452d91104194911ccc52a65a8a15deef2768fb3b243e440d25a3f6fc993a1  README.md
```
