# Courier Symphony — Brand Visual System

Status: public-facing visual direction. No confidential infrastructure details in public visuals.

## Existing visual assets

Current repository assets:
- studio/assets/hq_room_bg.jpg
- studio/assets/hq_room_bg.png
- studio/assets/hq_room_bg_hd.jpg

These are useful starting assets, but they are not yet a complete company brand pack.

## Public visual principle

Courier Symphony should look:
- premium
- technical
- calm
- dark / high-contrast
- evidence-driven
- modern without generic AI clichés

Avoid:
- AWS console screenshots
- account IDs, IP addresses, keys, tokens, security-group details
- internal worker window screenshots
- fake customer logos
- fake metrics
- copied competitor branding
- generic glowing-brain / robot stock imagery

## Core brand image set to build

1. Company hero image
   - abstract AI operations control room
   - orchestration lanes / verified execution
   - subtle sense of scale
   - no sensitive data

2. Public progress-update card
   - Courier Symphony wordmark
   - short headline
   - 3–4 verified progress themes
   - reusable social template

3. Architecture teaser
   - simple visual:
     TASK -> EXECUTE -> VERIFY -> RECONCILE -> DONE
   - public-safe, no infrastructure identifiers

4. Reliability / trust visual
   - show states such as RUNNING, VERIFIED, BLOCKED, UNKNOWN
   - emphasize fail-closed behavior

5. Cloud / scale visual
   - neutral cloud-worker abstraction
   - do not imply formal AWS/Meta partnership unless documented

6. Website hero background
   - premium dark spatial scene
   - subtle nodes / lanes / execution traces
   - visually distinct from Atlas and other competitors

7. Funding / due-diligence visual
   - clean system diagram
   - measurable milestones / evidence
   - suitable for grant decks and reviewer pages

## Today's recommended public image

For the 20 September 2026 progress update:

Headline:
"Building reliable AI operations."

Subline:
"Traceable. Recoverable. Cost-aware. Built for unattended work."

Visual:
A dark, premium Courier Symphony control-room composition with a central execution lane:
TASK -> VERIFY -> RECONCILE -> DONE

Do not show actual AWS screens, IPs, IDs, account data, or confidential architecture.

## Copyright / originality

Use only:
- original Courier-created visuals
- properly licensed assets
- public-domain assets where appropriate

Do not clone competitor artwork or visual identity.

Ideas and patterns may inspire the design, but the final visual language must be recognizably Courier Symphony.

## Signature motion: red beam, green proof (since 2026-10-04)

From the first product video: a storm of windows, the bird removes the noise
with a red beam, and only the real work stays, linked by green lines.

| Colour | Meaning | Rule |
|---|---|---|
| RED beam | actually closed / reclaimed / failed | only what `reclaim()`/`reconcile()` really closed |
| GREEN proof | verified done, or safely reused | no shadow, no claim |
| AMBER | waiting (human, OS, wake, capacity) or parked | never shown as done |
| BLUE | working, outcome not yet proven | |
| GREY | unknown / orphaned / not ours | shown, never touched |

The single source of truth is `courier_runtime/visual_language.py`;
`tests/test_visual_language.py` fails if a runtime state has no colour, so
every future overlay, video and status page keeps this language.
Video ending: the green state stays on screen last.
