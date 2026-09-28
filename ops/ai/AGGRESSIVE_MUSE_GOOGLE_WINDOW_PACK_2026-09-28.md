# Aggressive Muse + Google Window Pack — 2026-09-28

Muse Round A:
- windows 11-20 use ops/ai/muse_aggressive20/MUSE_A_*.txt

When A is done:
- windows 1-10 use ops/ai/muse_aggressive20/MUSE_B_*.txt

Google Windows single-worker queue:
- enqueue ops/ai/google_windows_batches/GOOGLE_BATCH_01..15 in order
- repeat 12-15 as sweep prompts after 01-11 complete

Rules:
- Ledger complete
- one PRE_CODEX durability owner only
- no unchanged PRE_CODEX revalidation
- no physical runs from Muse/Windows Google
- no third-party tool repair
