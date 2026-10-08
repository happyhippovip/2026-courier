# Canonical work queue

Workers claim work from one ledger-backed queue. A prompt file with a hand-maintained pool is not the source of truth.

The catalog is `registries/work_items/*.json`, one item per file, checked against `courier_core/schemas/work_item.schema.json`. Claim, renew, and release events append to a JSONL ledger (`--ledger`). Seed files stay as published. They are not rewritten when someone claims an item.

`python -m courier_core.work_queue` does not call the controller and does not import `courier_worker`.

## Commands

```bash
python -m courier_core.work_queue next --holder window-a --ledger /path/to/queue.jsonl
python -m courier_core.work_queue claim --item REPORT-QA --holder window-a --ttl 3600 --host local --done-pr 281 --ledger /path/to/queue.jsonl
python -m courier_core.work_queue renew --item REPORT-QA --holder window-a --ttl 3600 --ledger /path/to/queue.jsonl
python -m courier_core.work_queue release --item REPORT-QA --holder window-a --result "draft PR" --ledger /path/to/queue.jsonl
python -m courier_core.work_queue spawn --template P9 --module worker_tokens --ledger /path/to/queue.jsonl
```

`next` prints the lowest-id ready item and a prompt for an interactive window. It does not claim. Claim before writing. Pass `--open-pr-file` once per path changed by an open pull request, and `--done-pr` once per merged pull request a dependency names. `spawn` turns the P9 template into one `P9-<module>` item.

Exit 0 means the command ran. `NO_READY_ITEM` means the queue has nothing to offer. Exit 2 prints a short code and no traceback.

## Ready, claim, lease

An item is ready when:

- its effective status is `READY`, or an ordinary claim lease is already expired
- every `depends_on` entry is a `DONE` item or a pull-request number passed in `done_prs`
- its `files_scope` does not overlap an unexpired `CLAIMED` item
- its `files_scope` does not overlap an open pull request path given by the caller

`claim` is atomic under a lock on the ledger. The same holder claiming an unexpired lease again is a no-op and does not append. A different holder is rejected. An expired lease can be claimed again. `renew` extends a lease the holder still owns. `release` records a short result and sets `DONE`. A second release with the same result is a no-op.

`DONE` and `BLOCKED` seeds stay that way. Ledger events do not reopen them.

A seed marked `CLAIMED` with a pull request number, or with a lease that has no expiry, stays claimed until that holder releases it. The clock does not put it back on the queue. `P9` is a template: it is not claimable. `spawn` appends one `P9-<module>` item whose `files_scope` is `tests/` only. That child can be claimed once. After the lease ends it stays unavailable, and it does not keep occupying `tests/`.

## Seeded pool

| id | status | why |
| --- | --- | --- |
| P1 | DONE | pull request #277 |
| P2 | CLAIMED | pull request #287; `publish_gate` is `explicit_human_approval` |
| P3 | CLAIMED | pull request #298; no network, no credentials, visibility private |
| P4 | CLAIMED | pull request #301; no network, no credentials, inbox-draft only |
| P5 | DONE | pull request #282 |
| P6 | CLAIMED | pull request #304, branch `lane/L2-worker-tokens-P6` |
| P7 | DONE | pull request #281 |
| P8 | CLAIMED | pull request #309, branch `lane/L5-hub-mission-list-P8`; depends on #272; stack on `lane/L2-receipt-read-model` |
| P9 | template | spawns `P9-<module>`, each claimable once, `files_scope` `tests/` only. Pull request #312 built the retired one-off audit title; that title is not a ready item |
| WK7 | CLAIMED | holder `cloud:lane/L3-local-veto`, pull request #305; do not edit #141 files |
| REPORT-QA | READY | depends on #281; tests only |

## Interactive feeders

Host feeders must claim through this queue once it has landed. A branch that already exists is not a claim.

```bash
python -m courier_core.work_queue claim --item <id> --holder <holder> --ttl 86400
```

Call `claim` once per item the feeder hands to an interactive session. Do not keep a separate branch-exists claim.
