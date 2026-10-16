# MMAC-203 — U5 linkage resolved, L3/#231 merge-order finding (resume, read-only)

Base `origin/integration/v1` = `f425d328`. Zero mutations. (Note: this workspace's checkout sits on the foreign `lane/L3-google-builder-worker` branch with peer scratch files — left completely alone; all reads via `git show`.)

## U5 producer-linkage trace: upgraded, one half still open
- Consumer wired: `scripts/google_builder_worker.py` (lane L3, commit `fd678a950`, 04:41 CEST) calls `queue.get_admissible_packet` (:471), `evaluate_packet` (:374), and mints `WorkPacket`s (:514). Its tests execute real file/test tasks against tmp evidence dirs (mock only for env paths).
- Mechanism proven: #231 single-writer battery (MMAC-198).
- Still open: who mints packets FROM ledger state (the ledger→`add_packet` call site) — untraced.
- Verdict: U5-PARTIAL → mechanism-proven-plus-consumer-wired.

## New finding: L3 × #231 merge-order interaction (owner: L1 + L3 owner, no patch from here)
L3's `work_packet.py` edits sit on the pre-#231 base: adds `payload`, keeps wake-to-CURRENT and no CURRENT normalization, adds separate per-packet locks. #231 rewrites the same functions with `parked_from` + normalization but no `payload`. Second merger must reconcile all three — else the builder inherits the double-CURRENT-on-wake hole or drops payloads.

## Windows news
PR #245 pytest windows PASS (10m14s, 8m50s) → fully green, merge-ready. #240/#246 windows still pending (not polled).
