# Mission 142C — Chief Brain and zero-copy-paste contracts

Status: DESIGN_ONLY. These contracts do not claim a normal Chief chat, Google, or Codex provider can be automatically invoked today.

## Current targeted inventory

| Component | State | Evidence / boundary |
|---|---|---|
| Courier envelopes, IDs and correlation | IMPLEMENTED | existing Courier schemas and dispatch events |
| Chief Commander and SmartResourceRouter | IMPLEMENTED | `scripts/run_chief_commander.py`; active local route call |
| Autonomous loop/supervisor/checkpoints | PARTIAL | deterministic local paths exist; normal-Chief ingress is unproven |
| Thought Curator / context snapshots | IMPLEMENTED | local event/context-snapshot tooling; not a normal-chat listener |
| Native Codex attachment | IMPLEMENTED_BOUNDED | historical local bounded worker evidence only |
| Google/Antigravity automatic adapter | UNPROVEN | no verified official unattended trigger/result return |
| Provider-independent result transport | PARTIAL | Courier structures exist; canonical `PROVIDER_RESULT_V1` is designed here |
| Publication authority | BLOCKED | 140C critical remediation remains open |

## Context selection

`DELTA_CONTEXT` is default: select only task-scoped files, policy/security contracts, relevant decisions, latest compatible result and hashes. Exclude superseded decisions unless the task explicitly audits history. `UNCHANGED_FILE_RESEND`, full-chat resend and full-repo resend are forbidden except when a documented dependency/risk gate requires them.

## Routing and cost policy

States: `GOOGLE_BUILD`, `CODEX_REVIEW`, `LOCAL_DETERMINISTIC`, `HUMAN_GATE`, `WAIT_EXTERNAL`, `IDLE`. Use local deterministic work first. Reserve Codex for bounded independent verification. Route heavy visual/broad work to Google only when an official provider path is available. Provider failure, quota uncertainty, rate limit, invalid result or timeout parks only the affected branch. A reviewer never becomes the builder for high-risk security work.

Provider quota is observational metadata: `UNKNOWN`, `AVAILABLE`, `LIMITED`, `NEAR_LIMIT`, `EXHAUSTED`, `RESET_PENDING`; it is neither currency nor compute metering. All unknown incremental cost is `PAYMENT_APPROVAL_REQUIRED`; `AUTONOMOUS_SPEND_LIMIT_EUR=0` cannot be overridden by Chief, worker or provider.

## Continuation and safety

`RESULT → validate → classify → durable checkpoint → choose next allowed action → build context package → route → dispatch → await result`.

Terminal states: `DONE`, `BLOCKED`, `WAITING_EXTERNAL_REVIEW`, `WAITING_FOR_USER`, `AUTH_REQUIRED`, `CONFIG_REQUIRED`, `PLATFORM_BOUNDARY`, `PAYMENT_APPROVAL_REQUIRED`, `IDLE`.

Require task/result/diff/test fingerprints, `MAX_ITERATIONS`, bounded retries, one heavy job, cooldown, circuit breaker, heartbeat, watchdog and backpressure. Identical code+test hashes reuse a prior review; high-risk changes require independent review. Human gates pause only their branch.

## Human gates and claims

Human-only categories: money, identity/KYC, legal declaration, CAPTCHA, hardware key, new consent, audience decision, publication approval and private-upload approval. Ordinary reusable authorized OAuth is not automatically a Human gate, but no security mechanism may be bypassed.

Creator claims are labeled `SOURCE_SUPPORTED`, `EXTERNALLY_VERIFIED`, `INFERENCE`, `HYPOTHETICAL`, `FICTIONAL`, or `UNKNOWN`. Fiction stays fiction; unavailable analytics stays `ANALYTICS_NOT_AVAILABLE`.

## HQ and post-141G review

HQ is observability only: `SELECTED`, `RUNNING`, `WAITING`, `REVIEW`, `BLOCKED`, `DONE`, `IDLE` must arise from canonical state; animation triggers no model call.

After the builder stops changing 141G files: fetch/compare, inspect only its delta, run all seven `test_mission_141c_acceptance_oracle` tests plus the 139G preservation suite, then independently verify T1/T2/A2/P1/O1/O2/O4/R1/R2. No approval is possible while any Oracle test fails.

## Current zero-copy-paste gaps

- `PROVIDER_API_GAP` / `UNPROVEN`: no verified normal Chief-chat ingress or automatic result delivery.
- `AUTH_GAP`: official provider authorization/trigger path remains unverified.
- `LOCAL_CODE_GAP`: no durable canonical Chief Brain/context/result contract writer/validator yet.
- `PRODUCT_UI_GAP`: HQ can display local Courier state but is not proof of external provider execution.
- `LOCAL_CODE_GAP`: 140C publication security findings must close before any activation.

## Minimal builder order

1. Result ingestion/validation; 2. context-package builder; 3. quota/cost-aware router; 4. official provider adapters; 5. durable Chief state; 6. continuation engine; 7. human-gate notification; 8. benchmark telemetry; 9. creator enrichment/novelty interfaces; 10. HQ mapping.
