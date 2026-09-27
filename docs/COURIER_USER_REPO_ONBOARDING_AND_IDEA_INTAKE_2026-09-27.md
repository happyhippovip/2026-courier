# Courier User Repo Onboarding & Idea Intake — 2026-09-27

Status: LATER / PRODUCT REQUIREMENT
Owner intent: make it easy for future users to bring their own ideas, projects, and repositories into Courier without becoming technical operators.

## Product intent

A future Courier user should be able to say, in effect:

> "Here is my project/repository. Here is what I want. Keep the useful work moving."

Courier should then:
- connect to the user's chosen repository through an authorized integration;
- read the permitted project context;
- preserve the user's goals and ideas as durable project truth;
- turn authorized ideas into structured goals/tasks;
- avoid duplicate or speculative work;
- keep results and decisions durable;
- ask the user only for genuine decisions, money, safety, or permissions.

The user should not need to understand internal worker, queue, ledger, model, or orchestration concepts.

## Critical privacy and security boundary

NEVER ask users to paste raw account passwords, API keys, personal access tokens, recovery codes, payment secrets, or authentication cookies into a repository or normal chat flow.

Preferred future connection model:
- OAuth / GitHub App / supported connector
- explicit repository selection
- least-privilege permissions
- revocable authorization
- visible permission scope
- clear separation between read-only and write access
- no hidden account switching
- no credential persistence in public repositories

A user may identify:
- repository
- organization/account handle
- project
- desired goal

But authentication secrets remain outside project content.

## Simple future user flow

1. CONNECT
   User connects GitHub or another supported project source.

2. CHOOSE
   User chooses the repository/project Courier may access.

3. GOAL
   User states what they want to achieve.

4. CONTRACT
   Courier summarizes:
   - desired result
   - allowed scope
   - forbidden scope
   - important constraints
   - proof/evidence expectation
   - human/money/safety gates

5. CONFIRM
   User confirms the Goal Contract once.

6. DURABLE INTAKE
   Courier stores durable project truth in an appropriate project-controlled location.

7. PLAN
   Courier converts the confirmed goal and existing project context into dependency-safe work.

8. EXECUTE / VERIFY / RECONCILE
   Work continues through the normal Courier model.

9. HUMAN ONLY WHEN NEEDED
   Courier returns for:
   - genuine decision
   - money
   - permission
   - safety/legal boundary
   - unresolved goal conflict

10. DONE / NEXT
   User sees:
   - what changed
   - what is verified
   - what remains
   - why work stopped
   - what happens next

## Idea inbox

Users should have a low-friction way to add ideas without automatically turning every idea into active work.

Each idea should become one of:
- NOW
- NEXT
- LATER
- PARKED
- REJECTED / NOT A GOAL

Default:
NEW IDEA != ACTIVE TASK

Courier should first classify:
- Does this support an existing goal?
- Does it reduce risk?
- Does it improve customer value?
- Does it create revenue/stability/freedom?
- What would it displace?
- Is it authorized now?

This prevents idea overload.

## Durable idea format

A lightweight future idea record can contain:

IDEA_ID=
TITLE=
USER_INTENT=
PROJECT/REPO=
WHY_IT_MATTERS=
RELATED_GOAL=
STATUS=
AUTHORIZED_NOW=YES|NO
NEXT_REVIEW=
NOTES=

Do not require users to fill technical metadata manually.

## Bring-your-own-repo principle

Courier should work with user-owned repositories rather than forcing all projects into Courier-owned repositories.

Principles:
- user retains repository ownership;
- Courier access is permissioned and revocable;
- Courier writes only within granted scope;
- existing project conventions are respected;
- one mutable scope has one active writer unless explicitly coordinated;
- the repository remains usable without Courier;
- Courier-specific metadata should be minimal and clearly separated from application code where possible.

## Suggested project bootstrap

For a newly connected project, Courier may later offer an optional lightweight bootstrap:

.courier/
  GOAL.md
  CURRENT.md
  IDEAS.md
  DECISIONS.md
  RESULTS/
  TASKS/

This is a PRODUCT CONCEPT, not a current implementation requirement.

The exact format must be validated against real pilot use before becoming mandatory.

## No-human-message-bus rule

The future customer must not become the normal relay between:
- models
- workers
- sessions
- tools
- machines

Normal result routing belongs to Courier.

## Account abstraction

Courier should treat the user's provider/repository accounts as connected capabilities, not as credentials the user repeatedly copies into prompts.

Future behavior should aim for:
- Connect once
- choose scope
- authorize
- revoke at any time
- Courier remembers the connection through its secure integration layer
- project truth remains independent of any single provider chat session

## Provider independence

The durable project state should not depend on one model/provider account.

A user can change:
- model
- provider
- machine
- session

without losing:
- goal
- decisions
- results
- proof
- current next action

## Import existing projects

For existing repositories:
- do not broad-scan by default;
- start from user-selected entry points or repository guidance;
- identify current goal and active work;
- respect existing issue/task systems if present;
- reuse existing results;
- avoid duplicating work already completed.

## Multi-repo future

Some goals may span multiple repositories.

This is LATER.

If added, Courier must:
- preserve explicit repo boundaries;
- keep permissions independent per repo;
- never assume write access across repositories;
- maintain traceable cross-repo dependencies.

Do not build this before single-repo pilot evidence.

## Customer-facing simplicity

Customer language should stay simple:

- Connect project
- Tell Courier what you want
- Courier works
- Needs you
- Done
- Proof
- Next

Avoid exposing:
- claim leases
- attempts
- worker IDs
- dispatch generations
- internal ledgers

unless needed for trust/debugging.

## Product priority

Classification: LATER until current core proof and pilot gates allow product expansion.

Do not interrupt:
1. final candidate proof
2. independent review
3. RUN_1
4. RUN_2
5. core freeze
6. first real pilot

This requirement becomes implementation-relevant when:
- core proof is stable;
- pilot feedback confirms repo/project onboarding is needed;
- the simplest secure integration path is known.

## First pilot version

The earliest pilot does NOT need fully automated repo onboarding.

Manual assisted setup is acceptable if measured.

Measure:
- setup minutes
- user confusion
- permissions friction
- number of manual relay steps
- support effort
- whether the user understands what Courier can and cannot change

Automate onboarding only after repeated friction is observed.

## Long-term product promise

Future ideal:

> Connect your project once. Tell Courier what you want. Come back later and see what actually happened.

The user's repo is durable project context.
Courier is the execution and coordination layer.
The user keeps control of goals, permissions, money, safety, and major decisions.

## Shared capability choices for connected user repositories

Canonical strategy: `docs/COURIER_SHARED_CAPABILITY_UPDATE_FABRIC_2026-09-28.md`.

Future onboarding should separately ask/record:
- whether the user wants to RECEIVE recommended shared capabilities;
- whether compatible optional capability packs may auto-install or require approval;
- whether the user wants to CONTRIBUTE selected generalized reusable capabilities;
- which project artifacts must always remain private;
- update channel preference (safe-auto/balanced/pinned/offline where supported).

Receiving and contributing are separate choices.

Courier must never interpret repository connection as permission to publish that repository's code/data into a shared library.

If a user's work appears reusable, Courier may propose:
PRIVATE WORK -> generalized/sanitized capability candidate -> explicit authority/rights check -> validation -> optional shared publication.

Other users receive only the generalized/versioned capability package, never the originating user's private repo/data.
