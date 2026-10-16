# Canonical work queue

Workers claim work from one ledger-backed queue. A prompt file with a hand-maintained pool is not the source of truth.

The catalog is `registries/work_items/*.json`, one item per file, checked against `courier_core/schemas/work_item.schema.json`. Claim, renew, and release events append to a JSONL ledger (`--ledger`). Seed files stay as published. They are not rewritten when someone claims an item.

`python -m courier_core.work_queue` does not call the controller and does not import `courier_worker`.

## Commands

```bash
python -m courier_core.work_queue next --holder window-a --ledger /path/to/queue.jsonl
python -m courier_core.work_queue claim --item P2 --holder window-a --ttl 3600 --host local --ledger /path/to/queue.jsonl
python -m courier_core.work_queue renew --item P2 --holder window-a --ttl 3600 --ledger /path/to/queue.jsonl
python -m courier_core.work_queue release --item P2 --holder window-a --result "draft PR" --ledger /path/to/queue.jsonl
```

`next` prints the lowest-id ready item and a prompt for an interactive window. It does not claim. Claim before writing. Pass `--open-pr-file` once per path changed by an open pull request, and `--done-pr` once per merged pull request a dependency names.

Exit 0 means the command ran. `NO_READY_ITEM` means the queue has nothing to offer. Exit 2 prints a short code and no traceback.

## Ready, claim, lease

An item is ready when:

- its effective status is `READY`, or its claim lease is already expired
- every `depends_on` entry is a `DONE` item or a pull-request number passed in `done_prs`
- its `files_scope` does not overlap an unexpired `CLAIMED` item
- its `files_scope` does not overlap an open pull request path given by the caller

`claim` is atomic under a lock on the ledger. The same holder claiming an unexpired lease again is a no-op and does not append. A different holder is rejected. An expired lease can be claimed again. `renew` extends a lease the holder still owns. `release` records a short result and sets `DONE`. A second release with the same result is a no-op.

`DONE` and `BLOCKED` seeds stay that way. Ledger events do not reopen them.

## Seeded pool

| id | status | why |
| --- | --- | --- |
| P1 | DONE | open pull request #277 |
| P2 | READY | no pool text in the repo; short neutral scope; acceptance is tests and a draft PR |
| P3 | READY | same |
| P4 | READY | same |
| P5 | DONE | open pull request #282 |
| P6 | READY | same as P2 |
| P7 | DONE | open pull request #281 |
| P8 | READY | same as P2 |
| P9 | READY | same as P2 |

Taken slots are `DONE`, not a lease, so an expired claim cannot put them back on the queue. Ready scopes are new files and do not overlap each other or the taken scopes.
