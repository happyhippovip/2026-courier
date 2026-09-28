# CRYPTOGRAPHIC HANDOFF LEDGER - STANDARD OPERATING PROCEDURE (SOP)

**VERSION:** 1.0 (2026-09-28)
**TARGET:** All Autonomous Agents (MUSE, COURIER, OPUS, GEMINI) and Human Operators.

## 1. THE GOLDEN RULE
The `ledger.jsonl` is the **absolute single source of truth** for task execution state. 
If a task is marked `RECONCILED` with a valid fingerprint, **DO NOT RE-RUN IT**.

## 2. EVIDENCE PATH INTEGRITY
Every entry in the ledger MUST map to an existing physical evidence file in the `ops/ai/wall_results/` directory.
- Directory paths are strictly forbidden as evidence targets.
- Missing files violate the cryptographic chain.

## 3. FINGERPRINTING (DO_NOT_REPEAT)
The `FINGERPRINT` field in `ledger.jsonl` MUST mathematically match the `DO_NOT_REPEAT_FINGERPRINT=` token located inside the evidence file.
- When generating a new result, compute a SHA256 of the output block.
- Inject `DO_NOT_REPEAT_FINGERPRINT=sha256-<hash>` into the result file.
- Write the exact same string into the `FINGERPRINT` key in the ledger JSONL.

## 4. ERROR HANDLING & LIMITS
If an API limit is hit or an error occurs:
1. Write the error state to the evidence file.
2. Mark the ledger status as `BLOCKED` or `FAILED`.
3. Do not spam the provider. Stop new work and release the claim.

## 5. PRE-FLIGHT & COMMITS
- Human Operators: Before you commit, the **git pre-commit hook** will automatically run `ledger_integrity_check.py`.
- If the hook fails, run `./ledger_repair.py` to auto-heal mismatched fingerprints.
- Never force-commit a broken ledger state (`--no-verify`).
