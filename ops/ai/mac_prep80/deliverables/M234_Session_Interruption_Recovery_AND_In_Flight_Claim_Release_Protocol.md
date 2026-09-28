# M234 — Session Interruption Recovery & In-Flight Claim Release Protocol

## 1. Overview & Authority
- **Task ID**: M234
- **Area**: SESSION_RECOVERY
- **Status**: COMPLETE

## 2. Recovery Protocol
- Claims older than lease expiration threshold without corresponding results are released back to READY.
- New session inspects existing claims before claiming new tasks.
