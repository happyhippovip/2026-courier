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
