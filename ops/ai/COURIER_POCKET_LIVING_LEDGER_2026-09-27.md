# Courier Pocket / Living Ledger — 2026-09-27

## Core idea
Courier is not another AI chat assistant.

**Muse creates. Courier delivers. Ledger proves.**

Courier's customer-facing character is a calm, living representation of the real Ledger. The customer should not have to watch terminals, agent windows, token streams, or copy/paste work between AI systems.

A courier's job maps naturally to the system:
- know what must go where;
- know what is already in transit;
- know what arrived;
- know whether delivery was verified;
- know when a real human decision is required.

The mascot therefore has a functional role, not merely decorative branding.

## Product promise
The customer states a goal. Courier coordinates available AI engines such as Muse and other permitted workers, preserves ownership/state/evidence, verifies results, continues when safe, waits when work is unnecessary or blocked, and interrupts the human only for a genuine human gate.

The customer sees calm truth while Courier manages complexity underneath.

## Minimal Pocket surface
The first mobile-friendly/read-only surface should be derivable from data Courier already needs. Do not create a second source of truth.

Show:
- project / goal;
- current phase;
- verified completed work;
- work currently active;
- waiting/blocked work and why;
- NEXT;
- NEEDS_ME: yes/no, with the exact decision/action if yes;
- resource/cost observation where available;
- work intentionally not started because it would be duplicate, unnecessary, blocked, or resource-expensive.

Example:

> 📦 Kerzen-Shop
> 🟡 Wird gebaut
> ✅ Logo fertig
> ✅ Startseite verifiziert
> 🔍 Zahlung wird geprüft
> 💰 beobachtete KI-Kosten: 0,18 €
> 💤 6 Arbeiten nicht gestartet — derzeit nicht nötig
> 👤 Von dir brauche ich gerade nichts

No invented percentages or fake progress bars.

## Return-after-away moment
The primary demonstration is not "look at many agents." It is:

1. User states a real project goal.
2. Courier starts once.
3. User leaves.
4. Courier safely continues through multiple useful steps.
5. User returns.
6. Pocket summarizes what happened, what is VERIFIED/RECONCILED, what waits, what was avoided, and whether the user is needed.

Desired language:

> Guten Morgen. Während du weg warst, habe ich 7 Schritte weitergebracht. 5 sind verifiziert. Einer wartet. Einen habe ich nicht gestartet, weil er unnötig Ressourcen verbraucht hätte. Ich brauche dich gerade nicht. Ich mache weiter.

Numbers must always come from actual Ledger state.

## Mascot state language
The Courier character should communicate state without requiring technical literacy.

Suggested semantic states:
- 📦 Auftrag angenommen — goal/contract exists
- 🚶 Unterwegs — useful execution active
- 🔍 Prüft — result received, verification pending
- ✅ Zugestellt — reconciled/verified completion
- 💤 Wartet — no useful runnable work / intentionally conserving resources
- ✋ Braucht dich — genuine HUMAN GATE
- 🛡️ Geschützt — work guarded due to safety/resource/conflict rule
- ♻️ Wiederverwendet — existing evidence/package/context prevented duplicate work

Visual design may change, but semantics must map to real Ledger states.

## Muse relationship
Muse should be treated as a high-value creation/work engine, not as the orchestration truth source.

Muse may create code, content, plans, images, or other artifacts. Courier decides when work is useful, packages the task, tracks ownership, receives results, sends them through verification, records evidence, and determines NEXT.

**Muse creates. Courier delivers. Ledger proves.**

Courier should make Muse more useful in long-running real projects by reducing human relay, repeated context, duplicate work, and unnecessary calls.

## Delivery-world metaphor
Use the metaphor consistently where it improves comprehension:
- project goal = delivery/order
- task/work package = parcel
- active execution = in transit
- result received = arrived, not yet necessarily accepted
- verification = inspection/proof of delivery
- reconciled = accepted delivery
- reusable verified capability = verified package
- HUMAN GATE = recipient/action required
- LFM = this delivery needs a person/capability
- LFG = person looking for a suitable project/delivery to help with

Do not let metaphor hide technical truth. RESULT_RECEIVED is never shown as verified delivery.

## Community extension
Later, verified community inventions can become reusable Courier packages.

A package should show provenance, version, permissions, compatibility and verification. Reuse should reduce repeated AI work.

LFG/LFM can use real Ledger needs rather than generic social posting: Courier can identify that a project genuinely lacks a designer, tester, domain expert, or other human capability and surface that need.

## Better additions

### 1. "Why did Courier do this?"
Every visible state/action should optionally expose a one-line reason derived from the Ledger:
- "Started because dependency X was verified."
- "Waiting because payment credentials require you."
- "Did not run another model because verified evidence already exists."

This creates trust without exposing machinery by default.

### 2. "Saved work" rather than speculative savings
Before controlled cost baselines exist, report concrete avoided actions:
- duplicate task suppressed;
- existing verified artifact reused;
- blocked job not launched;
- cached/reusable context used when measurable.

Do not translate avoided work into money unless measured.

### 3. Quiet-by-default notifications
Notify only for:
- real human gate;
- meaningful verified milestone;
- failure/blocker that stops useful continuation;
- completion.

Do not turn autonomous work into notification spam.

### 4. Shareable proof card
A user may share a compact card containing only non-sensitive facts:
- what was requested;
- what is verified;
- elapsed period;
- optional measured cost/resource facts;
- proof timestamp/version.

Never expose private prompts, credentials, internal secrets, or unverifiable marketing claims.

### 5. Accessibility / Grandma Test
Every Pocket state must have plain-language text, not rely on icon/color alone. A nontechnical user should answer:
- What did I ask for?
- What happened?
- Is it actually checked?
- Does Courier need me?
- What happens next?

### 6. Offline / low-data direction
Pocket should be data-light. Prefer compact Ledger deltas/state summaries over streaming agent transcripts. Cache the last trustworthy state locally where appropriate, clearly showing when it was last synchronized.

This supports low-bandwidth users and keeps the customer surface featherlight.

## First public demo
The smallest compelling demo:
- one real project;
- one start;
- at least one autonomous continuation;
- real verification;
- no human copy/paste relay between worker stages;
- user leaves and returns;
- Pocket truthfully summarizes progress and NEXT.

Do not require the full social world, package marketplace, or 37-slot visualization for this proof.

## Implementation boundary
This is a product/UI contract and future implementation target.

It MUST NOT expand the currently frozen five-file final correction scope or delay canonical RUN_1/RUN_2 proof.

Implementation order:
1. core autonomous proof;
2. read-only Pocket projection from existing Ledger;
3. return-after-away demo;
4. measured resource/cost facts;
5. reusable packages;
6. community/LFG-LFM extensions.

Pocket never becomes a second control plane. Ledger remains authoritative.
