# Wall V2 Publisher Protocol

Status: REQUIRED FOR GITHUB-FIRST DURABILITY

Only one PUBLISHER may publish wall coordination/spec artifacts at a time.

## Input

C:\Users\lol\courier_work\wall_v2\publish_queue

## Allowed destinations

Only explicitly prepared reusable wall/Ledger/queue/spec artifacts under:
ops/ai/

Application source is not published by this role.

## Process

1. acquire publisher lock
2. validate artifact has source package/result identity
3. reject credentials, secrets, raw provider tokens and secret-bearing payloads
4. reject duplicate identical artifact by fingerprint
5. fetch current destination when updating an existing file
6. publish one artifact at a time
7. record commit/ref and content fingerprint in local published metadata
8. update stable pointer only when the artifact explicitly supersedes the current generation
9. release lock when queue is empty or provider/tool blocks

## Conflict

If destination changed concurrently:
- do not overwrite blindly
- record PUBLISH_CONFLICT
- preserve both fingerprints
- continue other independent publish items when safe

## Human relay

Normal publication should not require the human to copy/paste artifact content.
