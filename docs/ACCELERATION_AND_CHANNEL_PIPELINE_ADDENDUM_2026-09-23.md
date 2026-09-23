# ACCELERATION + CHANNEL PIPELINE ADDENDUM
Stand: 23.09.2026

Purpose: Extend the existing Courier masterplan without rewriting or weakening it.

## Merksatz

**Schnell raus aus manueller Orchestrierung: Cannon V1 einfrieren, vorhandene Pipeline beweisen, danach den Bedienweg auf "Ziel + Kanal auswählen -> Courier arbeitet bis READY_TO_PUBLISH" verkürzen.**

This addendum does not override `docs/MASTERPLAN_COURIER.md`. If anything conflicts, the masterplan wins unless Dennis explicitly changes it.

## Current acceleration objective

Dennis should spend less time relaying prompts, checking windows and repeating context.

Desired near-term path:

1. Cannon V1 stable and frozen.
2. Existing content/channel pipeline inventoried once, not repeatedly rediscovered.
3. Existing channel/API setup status classified as BELEGT / BEHAUPTET / UNKNOWN.
4. A single operator flow prepared:
   - choose channel
   - describe desired story/content
   - choose/confirm template
   - Courier produces artifacts
   - independent/minimal verification
   - stop at human publish gate unless Dennis explicitly approves publication
5. Only after the above is proven: simplify UI/one-click customer path.

## Existing repository evidence — content pipeline

BELEGT in current branch:

- `scripts/run_content_production_pipeline.py` exists.
- It defines a local production flow for:
  - FruitKI / YouTube: IDEA -> SCRIPT -> ASSET_SELECTION -> VIDEO_BUILD -> REVIEW -> METADATA -> READY_TO_PUBLISH
  - 3D-KI / TikTok: IDEA -> HOOK -> SCRIPT -> 3D_ASSET_OR_SCENE -> VERTICAL_VIDEO_BUILD -> REVIEW -> CAPTION_HASHTAGS -> READY_TO_PUBLISH
- `config/social_channels.json` defines:
  - `chan-yt-fruitki` / YouTube
  - `chan-tt-3d-ai` / TikTok
- `config/content_workflows.json` defines both workflows and retains an explicit human publish gate.
- `studio/index.html` already contains a visual operator/studio surface.
- `docs/YOUTUBE_OAUTH_STEPS.md` documents a future/dry-run OAuth path and therefore is NOT sufficient proof that live YouTube publishing credentials currently work.

## API / credential truth rule

Dennis reports that Google-side APIs were connected. Treat that as **BEHAUPTET** until one small, safe, non-publishing health check proves each live integration.

Do NOT:
- reveal tokens or secrets;
- commit credentials;
- publish test content merely to prove auth;
- repeatedly re-authenticate working accounts.

Preferred proof later:
- provider health/auth status call with no publication side effect;
- redacted evidence only;
- one proof per provider, then reuse it.

## Product/operator target

The intended operator experience should converge toward:

`SELECT CHANNEL -> DESCRIBE STORY/GOAL -> SELECT/CONFIRM TEMPLATE -> RUN -> REVIEW EVIDENCE -> READY_TO_PUBLISH -> HUMAN APPROVAL -> PUBLISH`

The user should not need to understand worker routing, model windows, branch mechanics or internal prompts.

## Templates

Templates should capture reusable content structure, not hard-code one story.

Minimum template fields:
- target platform/channel
- format/aspect ratio
- target duration
- content style/tone
- hook structure
- story beats
- asset/render policy
- metadata/caption rules
- review criteria
- publish gate

## Credit / capacity policy

Do not burn model credits merely to prove that credits can be consumed.

Instead maximize **useful, evidenced work per credit** and record:
- tasks completed,
- wall-clock saved,
- human relays avoided,
- blockers caused by quota,
- backlog that could have run if capacity existed.

That creates a stronger evidence base for requesting more legitimate capacity than artificial consumption.

## Parallel-work rule while Cannon V1 is not frozen

Allowed in parallel:
- read-only inventory;
- documentation consolidation;
- identifying existing pipeline pieces;
- collecting exact commands and missing proofs;
- preparing a no-write gap map.

Not allowed in parallel:
- large new product features;
- conflicting writers;
- publishing;
- channel/account changes;
- architecture rewrites.

## After Cannon V1 freeze

Next acceleration package:
1. prove local pipeline end-to-end to READY_TO_PUBLISH;
2. prove channel selection maps to the correct workflow;
3. prove API/auth health without publishing;
4. prove template input produces the expected pipeline artifacts;
5. connect operator/studio surface to this path;
6. then test one explicitly approved real publication.

## Windows

Windows is a separate later acceptance lane. Do not let Windows interrupt the current Mac critical path unless a cross-platform blocker is proven.


## Google Mac execution prompts

For the current 7-worker Mac acceleration sequence, use:
`docs/GOOGLE_MAC_MASTERPROMPTS_ABC_2026-09-23.md`

Order: A -> B -> C. Each worker atomically claims one lane; do not assign duplicate review work.
