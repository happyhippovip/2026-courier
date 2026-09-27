# Courier V1 — Beginner Wall, Subscription-First UX, Community Surface — 2026-09-27

Status: PRODUCT VISION / NEXT AFTER CORE PROOF  
Authority: captures product intent; does not override current final-candidate, RUN_1, RUN_2 or writer rules.

## Product promise

Courier should be explainable by a non-technical user in one minute:

1. choose what you want done;
2. choose how much wall capacity you want;
3. Courier tells you what is actually active, guarded, waiting and verified;
4. you can leave it running and come back later;
5. you do not need to understand terminals, API keys or provider internals.

The product should feel powerful without looking like a developer console.

## Subscription-first experience

The normal customer path should NOT require API setup.

Preferred product model:

- consumer/customer uses a simple supported subscription/provider connection;
- Courier translates that into safe logical wall capacity;
- developer/API mode is optional and clearly separated;
- PAYG/API keys belong in an advanced/developer surface, not beginner onboarding.

Exact provider plan names, prices, entitlements and quotas are dynamic and must be read from current provider truth rather than hard-coded into product promises.

Goal:
A customer should be able to get real useful work from Courier using a normal provider subscription without ever creating an API key.

## Beginner wall control

Courier should expose wall capacity as a clean centered control, not as terminal windows.

Every integer remains technically selectable in the logical wall model.

Beginner-friendly visible presets should include at least:

- Wall 1
- Wall 3
- Wall 5
- Wall 6
- Wall 9
- Wall 10
- Wall 12
- Wall 16

Advanced mode may expose exact integer selection up to the current product maximum.

Why presets:
- Wall 1: minimal/single-agent use
- Wall 3: light starter
- Wall 5/6: useful everyday multi-agent work
- Wall 9/10: stronger workstation use
- Wall 12/16: larger machines / advanced users

These are REQUESTED logical slots, never guaranteed resident processes.

## Adaptive admission

Courier must decide what the machine can actually carry.

Example:

Requested Wall = 9
Admitted = 6
Active = 5
Waiting = 1
Guarded = 3

The UI should say this plainly.

Never imply:
"Wall 9 means nine heavy AI processes."

Prefer:
"Wall 9 means Courier may use up to nine logical work slots, while protecting your computer."

## Beginner language

Avoid exposing by default:

- process IDs
- provider auth state
- branch names
- token counters
- API key terminology
- internal retry mechanics
- raw task leases
- shell commands

Instead show:

- What you asked for
- What Courier is working on
- What is verified
- What is waiting
- Whether Courier needs you
- How much capacity is in use
- Estimated/actual provider cost where available
- Why work stopped, if it stopped

Advanced detail remains available behind an optional drawer.

## Visual layout

The main wall should be visually centered and calm.

Recommended structure:

TOP:
goal / project / status

CENTER:
wall capacity control
1 3 5 6 9 10 12 16
or exact selector in advanced mode

MIDDLE:
active crew cards / verified progress

BOTTOM:
needs-you / blocked / next / cost

The user should be able to hide the operational wall entirely.

## Focus / background mode

Provide a mode where the user can hide the wall/dashboard and see only:

- project background/world
- main chat
- people/team/community
- current goal
- lightweight status indicator

This lets Courier feel like a living work environment rather than a control panel.

The operational wall remains one click away.

## Community

Longer-term community surface may include:

- people helping on projects
- teams
- shared goals
- contributor profiles
- verified contribution history
- reputation based on real useful work
- project/community discussion
- opt-in discovery of useful people/skills

Do not turn this into fake social engagement or streak mechanics.

Verified useful contribution should matter more than activity volume.

## Contribution rewards / ownership concepts

The product may later explore contribution-linked rewards.

Examples of concepts to investigate:

- credits
- fee discounts
- supporter recognition
- project-specific reward pools
- revenue-share arrangements where legally valid
- regulated ownership/equity mechanisms only after proper legal structure

Hard rule:

Courier must NOT casually promise "shares", equity, investment returns, or ownership percentages to users.

Anything involving money invested in exchange for future ownership, profit participation, securities, revenue share or financial return requires a dedicated legal/compliance design before implementation or marketing.

Until then:
CONTRIBUTION_REWARD_CONCEPT=IDEA_ONLY
EQUITY_OR_INVESTMENT_PROMISE=NOT_AUTHORIZED

## Simple explanation requirement

The founder/operator must be able to explain each user-facing feature without needing internal architecture language.

If a product flow cannot be explained simply, it is not ready for beginner UI.

Grandma-test version:

"Choose how much help you want. Courier uses as much as your computer and plan can safely handle. It keeps working, checks what is really done, and tells you only when it needs you."

## Cost transparency

Show users:

- subscription/provider connection in plain language
- optional API/PAYG mode only in advanced settings
- current known usage/cost where provider exposes it
- wall throttling due quota/cost
- no hidden autonomous purchases
- no autonomous upgrades
- no automatic spend increase without explicit user approval

## Provider ladder

Courier should support a provider ladder rather than forcing one purchase path.

Conceptually:

FREE / INCLUDED CAPACITY
-> SUBSCRIPTION CAPACITY
-> HIGHER SUBSCRIPTION CAPACITY
-> OPTIONAL PAYG/API CAPACITY
-> PREMIUM REVIEW CAPACITY

Routing should choose the cheapest suitable proven option for each task.

Exact provider/model plan mapping is configuration, not product law.

## Model roles

High-capability models should be used where they materially matter:

- convergence
- difficult code-grounded review
- final architecture judgment
- critical contradiction resolution
- release readiness

Cheaper/faster models handle:

- broad read-only evidence work
- repetitive static audits
- result harvesting
- deduplication
- routine trace work

Do not burn premium capacity on work a cheaper model can safely complete.

## V1 product order

Still preserve:

FINAL CANDIDATE
-> TARGETED TESTS
-> INDEPENDENT REVIEW
-> RUN_1
-> RUN_2
-> MINIMUM HONEST UI

Then prioritize:

1. beginner Wall control
2. truthful admission/guarding
3. zero-human result harvesting
4. simple subscription-first onboarding
5. optional advanced/API mode
6. focus/background mode
7. community shell
8. contribution reward research
9. legally reviewed financial/ownership concepts only if still wanted

## Success metric

Courier is succeeding when a beginner can say:

"I choose how much help I want, give Courier a goal, and it keeps useful work moving without me managing twenty terminals."

Not:

"I learned how to operate twenty terminals."
