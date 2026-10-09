# Host loop

One host process claims ready work, runs a headless provider, checks the result, and continues. The work list is the canonical queue in `courier_core/work_queue.py` (draft PR #296). This loop does not keep a second catalog or a second claim ledger.

## Stack

`integration/v1` ← #267 `lane/L2-ledger-v1-bridge` ← #280 `lane/L2-bridge-restart-matrix` ← this branch, with #266 `lane/L2-worker-provider-exec-adapter` and #296 `lane/L2-work-queue-seed` merged in. The loop calls those APIs. It does not edit them.

```bash
python -m courier_worker.host_loop --once --host-config host.json
python -m courier_worker.host_loop --forever --host-config host.json
```

Run it from the repo root so `courier_core` and `scripts` import. Tests for this loop are `tests/test_host_provider_loop.py`. `tests/test_host_loop.py` is the existing Kirby wake-consumer contract and is not part of this loop.

## Tick

1. Admission reads `measure_pressure()` on the process governor. `UNKNOWN`, `RED`, `ORANGE`, a raised error, or a missing governor skips the claim. The loop does not call `admit_job`, so it does not start that governor's recovery window. One in-flight item is the one heavy run on this host.
2. `list_ready` is called with the open-PR paths and done-PR numbers from the GitHub verifier. `None` from that verifier means the view is unknown, and the host does not claim. A path changed by an open PR hides every ready item whose `files_scope` overlaps it.
3. The first ready item is claimed with `claim(item, holder, ttl)`. The same holder claiming an unexpired lease again does not append. A different holder is rejected. When the remaining lease is shorter than the provider timeout, `renew` extends it once for that expiry.
4. Providers run in the host config order (`agy`, `muse`, `cursor-agent` unless the config says otherwise) through `provider_exec`. Sandbox flags stay inside that adapter. This loop never adds `--yolo`, `--disable-sandbox`, or `--dangerously-skip-permissions`. A provider marked unavailable, or with three consecutive failures, is skipped. `cursor-agent` is not on the provider_exec allow-list, so it is marked unavailable without launching. A relative `agy` binary is not taken from `PATH`.
5. Verification records the tests-command exit code. Acceptance `draft PR` also requires the item branch to exist remotely and a draft PR from it. Refused or no-op provider output is `FAILED` even when the process exits 0. Approval refusal is `BLOCKED` and does not fall through to the next provider.
6. `release(result)` appends the receipt and closes the item. The queue's release is terminal `DONE`; the outcome token in the result is `ACCEPTED`, `FAILED`, or `BLOCKED`, plus provider, PR url, head sha, and the test summary. The same result from the same holder does not append again. A local `home/run/host_loop_receipts.jsonl` mirrors that line and is not a queue.

`--forever` claims the next item immediately. An empty ready set sleeps 5, 10, 20, 40, then 60 seconds. Three items in a row whose every provider failed mark this host `BLOCKED` and the process exits 2. It does not keep restarting.

`home/STOP` exits 0 and does not claim or launch. An item whose provider already exited still gets its receipt. `home/PAUSE` does not claim new work; an item already claimed is still run so the lease is not abandoned.

Exit 0 is a finished tick, an empty queue, or STOP. Exit 2 is a blocked host. Exit 3 is a bad config.

## Restart

`home/host_loop_state.json` remembers the in-flight item and the phase: `claimed`, `provider_exited`, `receipt_appended`. A crash at those boundaries, or before the claim, resumes without a second claim, a second provider launch, or a second receipt.

## Not in this process

There is no live GitHub client here. Tests pass a fake verifier. Without one, open-PR paths stay unknown and the host does not claim. Real `agy` and `muse` binaries are not required for the tests.
