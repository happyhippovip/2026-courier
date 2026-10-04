# RELEASE RELIABILITY PLAN

## Goal
Establish a candidate-independent architecture for release delivery, ensuring the system can safely update, recover from failed updates, and manage cryptographic agility without relying on specific user shell features.

## 1. Install & Update Fabric
- **Delta/Dedupe Updates:** Future client updates must support delta-patching or deduplication. Given the Python environment, updates should leverage pre-compiled zipapps or minimal wheel distributions rather than pulling hundreds of megabytes of dependencies each time.
- **Atomic Swap:** All updates must be applied atomically (e.g., download to `.tmp`, verify checksum, then atomic directory rename or file replace).

## 2. Rollback & LKG (Last Known Good)
- **State Preservation:** Before any executable update, the system must backup the `auth.json` and any local queue state.
- **LKG Fallback:** If the new version crashes on startup, a watchdog must immediately revert to the LKG binary and report the telemetry flag `UPDATE_FAILED`.

## 3. Failure Recovery
- **Network Interruptions:** Any update download must support resume (`Range` headers) or restart gracefully without corrupting the local install.
- **Corrupt State Detection:** If the internal SQLite ledger (on the server) or the client config becomes corrupted, the system must isolate the corrupted file (e.g., `ledger.db.corrupt_123`) and start fresh, rather than crash-looping.

## 4. Crypto-Agility Inventory
- **Current Primitives:** We rely heavily on SHA-256 for artifact addressing (`artifact_store.py`) and fingerprinting.
- **Future-Proofing:** Ensure that all hash comparisons and storage paths prefix the hash type (e.g., `sha256:abcd...`). If we migrate to SHA-3 or BLAKE3, the system must seamlessly route artifacts to the correct sub-handlers.

Status: CANDIDATE_INDEPENDENT_PREP_COMPLETE
