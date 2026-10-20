# Courier Symphony — Public recovery checkpoint (2026-10-18)

> PUBLIC, NON-SECRET STATUS NOTE. This is not a backup of source code or proof of successful recovery. Agents must verify all claims before acting.

## Why this exists
The project owner reports temporary loss of access to some agent interfaces. This document allows other authorized Courier agents to find the recovery context without relying on the affected chat or computer.

## Grok Bot local execution issue
- On macOS and Windows, the application setting was shown as "Ask every time" ("Jedes Mal fragen"), while the bot's read-only access probe reported "Never" ("Nie").
- After restarting the macOS application, the bot still reported blocked local access at approximately 18:47 CEST, 2026-10-18.
- Support reply dated 2026-10-18 acknowledges this as a known issue being tracked. Reference: **T-H76336**. No fix or ETA was confirmed.
- Do **not** reset the bot computer, uninstall software, change accounts repeatedly, or assume that a UI problem implies data deletion.

## V27 source preservation — reported, NOT independently recovered
- Reported bot-local branch: `grok/v27-costgate-fixes`
- Reported HEAD: `faf57f77`
- Reported base: `bdd9abcc`
- Reported scope: 10 commits; 3,253 passing tests (agent-reported, not independently verified here).
- Reported recovery artifacts on the bot's own workspace:
  - `V27_faf57f77_on_bdd9abcc.bundle`
  - `README.md`
  - `SHA256SUMS`
- Reported bundle SHA-256: `e7c12f4ef95cb395c40a9899adc114cb8bb338a744a998143081dacc11906b5f`
- The bundle has **NOT** been uploaded to this repository by this checkpoint.
- Independent off-bot copy and restore verification: **UNKNOWN / NOT CONFIRMED**.
- Agents should seek the actual bundle from authorized attachments/storage, verify SHA-256 and `git bundle verify`, and report provenance. Do not invent recovered commits or claim the GitHub repo contains V27.

## Other interface issue (separate)
The purple Courier Symphony project entry reportedly disappeared from the Cursor mobile Projects list after an account switch, while some workspace/agent conversations remained visible. Cursor support reference: **T-H74146**. Project deletion is **NOT CONFIRMED**.

## Safe next actions for authorized agents
1. Read this note; classify information as REPORTED, VERIFIED, or UNKNOWN.
2. Locate the V27 bundle and independently verify it without exposing secrets or private content.
3. Prepare a minimal, private, recoverable copy in an already authorized storage location; verify hashes and restore feasibility. No unnecessary full repository backups.
4. Review repository state read-only and propose an integration plan; do not assume the V27 commits are on GitHub.
5. Escalate the local-execution defect using support ticket T-H76336; do not repeatedly reset/reinstall.
6. Report blockers and next safe workkey.

## Guardrails
`SINGLE_WRITER=YES`; `HEAVY_JOB_LIMIT=1`; `REAL_TRADES=0`; `WALLET_SIGNING=NO`; `AUTONOMOUS_SPEND_LIMIT_EUR=0`; `UNKNOWN_COST=BLOCK`. No unauthorized push/merge, spending, secret exposure, or destructive restore.

**This public checkpoint intentionally excludes account emails, private repository data, credentials, full chat transcripts, and the recovery bundle.**
