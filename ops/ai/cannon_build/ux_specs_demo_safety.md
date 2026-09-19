# Courier UX Specs — Demos, safety, platform, audits, founder (MUSE 52,63,68-note,82,100,103,106–150)

## Demo map (fake worker modes; all provenance FAKE_LOCAL, never REAL)
| MUSE | Demo | Fake mode | Expected |
|---|---|---|---|
| 109 | 5-min physical demo | success → crash_after_persist → restart | build identity, task, worker takeover, auto result binding, restart recovery, clean idle |
| 110 | Demo integrity | — | no prefilled/cached result, no manual relay, no mock-labeled-real, no edited evidence |
| 111 | First-run onboarding | success | project→goal→package→NORMAL→harmless demo→result→verification lesson; zero provider cost |
| 112 | Safe demo project | success ("Ordne 5 Textdateien nach Thema") | deterministic queue→worker→result→verification, no external API — TESTED 9/9 |
| 113 | Human gate demo | human_gate (delete outside test scope) | gate opens, nothing deleted, branch-local blocking — TESTED |
| 114 | Recovery demo | crash_after_persist | reconcile existing result, no second execution — TESTED |
| 115 | Unknown effect demo | unknown_effect | UNKNOWN_EFFECT, no retry, reconciliation view — TESTED |
| 116 | Fast fake demo | 2× two_lane | UI proves MAX_ACTIVE=2 overlap; no real-provider claim — TESTED |
| 117 | Scope conflict demo | 2× scope_guarded same path | A RUNNING, B WAITING_SCOPE; B starts after A — TESTED |
| 118 | Large import demo | large_import | 100000 records streamed, preview=10, provider_calls=0 — TESTED |
| 119 | Demo cleanup | — | cleanup only inside Courier test workspace + fixture IDs; no wildcard deletes |

## 106 — First defect mode (reviewer fields)
candidate · fixture · steps · expected · actual · evidence · minimal scope · owner.
One reproducible defect, not a 40-point wishlist.

## 107 — Repro pack template
REPRO_ID · candidate SHA/tree · OS · build · config digest · fixture · steps · expected
· actual · logs · IDs · screenshot optional · owner · minimal fix.

## 108 — Screenshot evidence policy
Screenshot shows visible UI state. It does NOT prove runtime identity, process ownership,
causality, provider execution, or absence of duplicate effect. Each claim needs its own evidence.

## 120/121/122 — Test data labeling, badges, provenance
All test data labeled TEST/FIXTURE/MOCK/SYNTHETIC, never shown as ACCEPTED work.
Badges REAL (provider receipt required; provider name alone proves nothing) · TEST · MOCK
· IMPORTED · UNKNOWN. Worker provenance FAKE_LOCAL/REAL_LOCAL/REAL_EXTERNAL/IMPORTED/
UNKNOWN shown on every result.

## 123/124 — Neutrality, brand safety
No hardcoded provider names in core flow; provider features stay adapter-specific.
No "official/partner/certified" for Muse without proof; neutral "Muse adapter".

## 125/126/128/129 — Connectors, auth, accounts, rate limits
Per-connector panel: READ/WRITE scopes, external actions, billing permission, auth status;
unknown capability = denied. AUTH_EXPIRED blocks only that worker, queue preserved, no
login-popup storms. No auto account rotation / quota evasion; multi-account needs explicit
account_id + routing policy + authorization. Replace "rotate/bypass/spam/forever" docs with
backpressure/cooldown/circuit/human decision.

## 130/131/132/133 — Updates, changelog, rollback, staging
UPDATE_AVAILABLE_IDLE · DEFERRED_ACTIVE_RUN · DEFERRED_NIGHT · BLOCKED_DIRTY · READY;
night run stays pinned. Changelog card: current/target build, changed scopes, test status,
compatibility, migration need, rollback readiness. Rollback receipt: failed candidate,
reason, activated LKG + identity, state preserved?, tasks reconciled?, blockers?.
Identities: SOURCE ≠ CANDIDATE ≠ STAGING ≠ ACTIVE ≠ LKG.

## 134/135/136/137 — Cross-platform
Matrix Windows/Mac: SHA·TREE·BUILD·RUNTIME_ID·OS·smoke·worker state·result binding·clean idle.
Same candidate only on real match. Known difference classes: path separators, case
sensitivity, file locks, process spawning, signals, line endings, packaging, permissions
(READ-ONLY audit: classes listed; per-line ownership is Google's platform work).
Windows/Mac process diagnostic shows PID·PPID·exe/start·execution_id·worker_id — no kill function.

## 138/139/140/142 — Crash, recovery, clean start, corruption
Crash report: loaded build, last canonical event, active executions, persisted results,
recovery action, redacted stack. Startup screen: N queued / N results / N gates recovered,
N executions need reconciliation, N unknown effects — never "everything restored".
CLEAN_START=PASS verified live on fresh ws (0 locks, 0 results, fake smoke written).
Corruption: CORRUPTION_DETECTED + affected store + backup + read-only recovery + diagnostic
export; no silent destructive repair.

## 144 — Concurrent UI write audit (READ-ONLY finding)
Writers found: server/app.py → STATE_FILE (atomic tmp+fsync+replace, verified lines 462–516);
scripts/mac_worker/daemon.py → task state files + current_provider_wait.json (plain "w"
writes, no atomic pattern visible). Whether STATE_DIR == STATE_FILE scope is unresolved —
Google must confirm no shared file is written by both; daemon writes should adopt the
same tmp+fsync+replace pattern. OWNER: Google. SEVERITY: medium.

## 145/147/148 — Dashboard truth, zero invariants, clean idle pack
Every dashboard value documents canonical source + calculation + cache + freshness.
Queue=0/Running=0/Waiting=0 proves NO orphan/unknown-effect/full-verification by itself.
Clean idle template: RUNNING_EXECUTIONS=0, PENDING_RESULTS=0, ORPHAN_WORKERS=0,
UNKNOWN_EFFECTS=0, UNAUTHORIZED_LOOPS=0, TEMP_LAUNCHERS=0, PENDING_GATE_COUNT=,
QUEUE_READY_COUNT= → CLEAN_IDLE decision.

## Read-only audit findings (52,63,82,100,103,143)
- 52 claim scan: sync scripts print READY/PASS on copy success; no runtime identity check
behind them → false-green risk documented, owner Google. No ACCEPTED/LIVE/PRODUCTION
claims found in server runtime paths.
- 63 impossible states: goal DONE set at app.py:1289,1476 — binding to result not verified
in this pass (needs Google check); no VERIFIED/ACCEPTED states exist in runtime yet
(spec-only, cannot be falsely reached). AVAILABLE-without-connection: worker registry
path must require handshake evidence (spec §51 mandates it).
- 82 result backlog: no unbounded in-memory result lists found in sampled paths; full audit
needs Google (queue depth under burst not measured).
- 100 auto-upshift: no 1→2/2→3 auto-upshift logic found in server/app.py or
courier_continue.py — PASS (policy holds; auto downshift allowed).
- 103 log audit: minimal logging (6 print/console in app.py; daemon logs status lines only,
no result/artifact/token payload logging found) — PASS with retention policy still open.
- 143 atomic writes: app.py tmp+fsync+replace PASS; daemon plain writes — see §144.

## 149 — Founder morning dashboard (one screen)
Top: Was wurde geschafft? Then: Blocked · Needs me · Spend · Candidate · Workers ·
Results · Top defect. Bottom: NEXT SAFE ACTION. No dev noise.

## 140-note
CLEAN_START=PASS (fresh /tmp ws, 0 locks/results, fake smoke ok) — covers the test-workspace
half; device-level halves (no old workers/locks on Mac/Windows runners) remain Google R3.
