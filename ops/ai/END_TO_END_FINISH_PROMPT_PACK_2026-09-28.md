# Courier End-to-End Finish Prompt Pack — 2026-09-28

Goal: work from current Ledger/gate state toward a truthful finished product without skipping gates.

## Order
F01-F10 Ledger
F11-F14 gate / PRE_CODEX / Codex
F15-F23 Mac physical proof
F24-F27 Core Freeze
F28-F30 minimum real pilot
F31-F35 Product Shell after positive pilot
F36-F40 release/update/final handoff

## Model/host defaults
- Google Windows: C0/C1 deterministic/bulk and packets
- Google Mac: proof prep / restart / evidence
- Muse: C2 independent QA
- Opus 4.6: C4 convergence only
- Codex: exactly once per authoritative gate fingerprint
- Windows Antigravity: authorized source writer
- Mac Antigravity: physical RUN owner

## Current blocker
At creation time PRE_CODEX is DURABILITY_PENDING because reported FINAL_SHA is not remotely resolvable. F11 has one owner only; unrelated Ledger/proof-prep work continues.

## Files
- `ops/ai/finishpack/F01_GOOGLE_LEDGER_HARVEST_CLOSE_PROMPT.txt`
- `ops/ai/finishpack/F02_GOOGLE_LEDGER_IDENTITY_PERSISTENCE_PROMPT.txt`
- `ops/ai/finishpack/F03_GOOGLE_LEDGER_REPLAY_TRUST_PROMPT.txt`
- `ops/ai/finishpack/F04_GOOGLE_LEDGER_MOTOR_PROMPT.txt`
- `ops/ai/finishpack/F05_GOOGLE_LEDGER_CLAIM_CONTINUITY_PROMPT.txt`
- `ops/ai/finishpack/F06_GOOGLE_LEDGER_COST_PROOF_PROMPT.txt`
- `ops/ai/finishpack/F07_MUSE_LEDGER_QA_PROMPT.txt`
- `ops/ai/finishpack/F08_MUSE_LEDGER_RESTART_QA_PROMPT.txt`
- `ops/ai/finishpack/F09_OPUS_LEDGER_CONVERGENCE_PROMPT.txt`
- `ops/ai/finishpack/F10_GOOGLE_LEDGER_FINISH_GATE_PROMPT.txt`
- `ops/ai/finishpack/F11_GOOGLE_GATE_PERSISTENCE_PROMPT.txt`
- `ops/ai/finishpack/F12_GOOGLE_PRE_CODEX_PACKET_PROMPT.txt`
- `ops/ai/finishpack/F13_CODEX_HIGH_ONCE_PROMPT.txt`
- `ops/ai/finishpack/F14_GOOGLE_CODEX_RESULT_HARVEST_PROMPT.txt`
- `ops/ai/finishpack/F15_GOOGLE_MAC_EXACT_BINDING_PROMPT.txt`
- `ops/ai/finishpack/F16_GOOGLE_MAC_RUN1_PREP_PROMPT.txt`
- `ops/ai/finishpack/F17_MUSE_RUN1_QA_PROMPT.txt`
- `ops/ai/finishpack/F18_OPUS_RUN1_MINIMALITY_PROMPT.txt`
- `ops/ai/finishpack/F19_MAC_PHYSICAL_RUN1_PROMPT.txt`
- `ops/ai/finishpack/F20_GOOGLE_RUN1_HARVEST_PROMPT.txt`
- `ops/ai/finishpack/F21_GOOGLE_MAC_RUN2_PREP_PROMPT.txt`
- `ops/ai/finishpack/F22_MUSE_RUN2_QA_PROMPT.txt`
- `ops/ai/finishpack/F23_MAC_PHYSICAL_RUN2_PROMPT.txt`
- `ops/ai/finishpack/F24_GOOGLE_CORE_FREEZE_ASSEMBLER_PROMPT.txt`
- `ops/ai/finishpack/F25_MUSE_CORE_FREEZE_QA_PROMPT.txt`
- `ops/ai/finishpack/F26_OPUS_CORE_FREEZE_JUDGE_PROMPT.txt`
- `ops/ai/finishpack/F27_GOOGLE_CORE_FREEZE_COMMIT_PROMPT.txt`
- `ops/ai/finishpack/F28_GOOGLE_PILOT_PREP_PROMPT.txt`
- `ops/ai/finishpack/F29_MUSE_PILOT_QA_PROMPT.txt`
- `ops/ai/finishpack/F30_OPUS_PILOT_UNLOCK_PROMPT.txt`
- `ops/ai/finishpack/F31_GOOGLE_PRODUCT_SHELL_PACKET_PROMPT.txt`
- `ops/ai/finishpack/F32_OPUS_PRODUCT_SCOPE_PROMPT.txt`
- `ops/ai/finishpack/F33_WINDOWS_PRODUCT_WRITER_PROMPT.txt`
- `ops/ai/finishpack/F34_GOOGLE_PRODUCT_ACCEPTANCE_PROMPT.txt`
- `ops/ai/finishpack/F35_MUSE_PRODUCT_QA_PROMPT.txt`
- `ops/ai/finishpack/F36_GOOGLE_RELEASE_READINESS_PROMPT.txt`
- `ops/ai/finishpack/F37_GOOGLE_UPDATE_FABRIC_PREP_PROMPT.txt`
- `ops/ai/finishpack/F38_MUSE_UPDATE_PRIVACY_QA_PROMPT.txt`
- `ops/ai/finishpack/F39_OPUS_RELEASE_PRODUCT_JUDGE_PROMPT.txt`
- `ops/ai/finishpack/F40_GOOGLE_FINAL_PRODUCT_HANDOFF_PROMPT.txt`

Do not run a later-gated prompt before its PRECONDITION is durably true.
