---
description: "Run Courier autonomous finish loop without timer until DONE/quota checkpoint/real blocker."
---

Read `.agents/rules/00-courier-autonomy.md` first.

Use CURRENT Git and canonical Courier runtime state. Do not trust stale chat SHAs or old timeboxed queue prompts.

Continue the existing release objective autonomously. Repeatedly find the FIRST causal blocker, make the smallest safe fix inside current writer scope, run the SAME executable proof again, commit/push durable fixes, and continue without returning to the user between iterations.

Do not stop after one grep/search/test/fix/commit/task/gate/milestone. Do not apply old 15/30/45/60-minute, multi-hour, iteration-count, or "do not start next gate" clauses.

Stop only for PHYSICAL_ACCEPTANCE_PASS/DONE, PROVIDER_QUOTA_EXHAUSTED_CHECKPOINTED, HUMAN_REQUIRED, MONEY_REQUIRED, SAFETY, PERMISSION, or UNRESOLVED_WRITER_COLLISION.

No unattended merge. No second scheduler/server/verifier/truth authority. No broad process-name kills. No quota/rate-limit bypass or credential scraping.
