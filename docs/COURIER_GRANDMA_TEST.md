# COURIER GRANDMA TEST — Product Communication Law

Status: REQUIRED
Date: 2026-09-26

## Core rule

**If a non-technical person cannot understand what Courier accomplished, the product is not yet simple enough.**

This is called the **Grandma Test**. It is shorthand for universal clarity, not an assumption about age or ability.

Courier may be technically complex internally. The visible product must not require the user to understand that complexity.

## Daily update contract

Every daily update must begin with a plain-language summary before technical detail.

Required format:

### GRANDMA_UPDATE

**AUFTRAG:** What was supposed to happen?

**ERLEDIGT:** What actually finished?

**BEWEIS:** What real evidence proves it?

**MENSCH MUSSTE EINGREIFEN:** How many human interventions were required?

**ALS NÄCHSTES:** What will Courier do next?

Rules:

- ordinary language first
- technical language second
- no fake metrics
- no simulation described as physical proof
- no provider/model names unless they materially help understanding
- if nothing useful finished, say that directly
- if a human gate blocked progress, explain the gate in normal words
- if a result is still UNKNOWN, say UNKNOWN

## Demo contract

A demo is not successful because many terminals are visible.

A demo is successful when a non-technical viewer can see:

1. what was asked;
2. what got done;
3. what was checked;
4. how much human intervention was needed;
5. what started next automatically.

Preferred visible timeline:

`09:00 Auftrag gestartet`
`09:05 Schritt 1 erledigt + geprüft`
`09:18 Schritt 2 automatisch gestartet`
`09:40 Schritt 2 erledigt + geprüft`
`Menschliche Eingriffe: 0`

Only real runtime evidence may supply these values.

## Product-design implication

Every screen should have two layers:

### Layer A — Human outcome

- Mission
- Current progress
- Finished work
- Verified work
- Human attention needed
- What happens next

### Layer B — Technical evidence

- IDs
- provider/model
- task/attempt/dispatch identity
- runtime/process evidence
- logs
- fingerprints
- tests
- resource metrics

Layer A must stand on its own.

## Acceptance test

A feature passes the Grandma Test only when a non-technical person can answer:

- What did I ask the computer to do?
- What did it finish?
- How do I know it is really finished?
- Did I have to help it?
- What will it do next?

If those answers require internal jargon, simplify the product or the explanation.

## Relationship to other rules

Rule #1: **CONTINUE BY DEFAULT**
Courier keeps working when safe and allowed.

Rule #2: **FEATHERLIGHT BY DEFAULT**
Courier should accomplish useful work without making the computer feel overloaded.

Rule #3: **THE GRANDMA TEST**
Courier must make its value obvious in ordinary language.

Together:

> Start it once. It keeps going. The computer stays usable. Anyone can understand what got done.


## The Tomorrow Test

The Grandma Test is not only about explaining Courier. It must produce something visibly understandable the next day.

Every meaningful workday should end with a simple answer to:

> **"Was kann ich morgen jemandem zeigen, das gestern noch nicht da war?"**

The answer must be one or more visible outcomes such as:

- a finished file, report, page or feature;
- a before/after comparison;
- a real task timeline showing what finished automatically;
- a verified result with a simple PASS/NOT YET PROVEN label;
- a restart/recovery proof;
- a visible counter based on real runtime evidence;
- a one-minute demo that works without technical explanation.

A day with only internal discussion is not enough for the Tomorrow Test unless the discussion closed a real decision or removed a blocker that can be shown plainly.

### Required end-of-day Grandma Card

Every important day should produce one plain-language card:

**GESTERN:** What was not working or not proven?

**HEUTE:** What changed?

**SICHTBAR:** What can another person actually see?

**BEWEIS:** What proves it is real?

**OHNE MEINE HILFE:** What continued without manual intervention?

**MORGEN:** What is the next visible outcome?

If the answer to **SICHTBAR** is "nothing yet", say so honestly and state the nearest real proof still missing.

## The One-Minute Show Test

A non-technical person should be able to understand the day's progress in under one minute without reading logs.

Preferred order:

1. show the original task;
2. show the finished result;
3. show the evidence/check;
4. show what started next automatically;
5. show how many human interventions were required.

If the viewer needs an explanation of models, credits, providers, terminals or internal architecture before understanding the value, the visible product layer is still too technical.
