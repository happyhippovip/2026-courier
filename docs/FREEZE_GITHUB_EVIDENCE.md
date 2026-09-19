# GitHub integration freeze evidence

This is a reference map, not a new certification. At work start, `origin/main`
was verified as [`7004d817abf080a135da27cbc8faf4ddf60210b8`](https://github.com/happyhippovip/2026-courier/tree/7004d817abf080a135da27cbc8faf4ddf60210b8).

| Current-main proof | Reference |
| --- | --- |
| Bounded hosted worker | [`.github/workflows/courier_worker.yml`](https://github.com/happyhippovip/2026-courier/blob/7004d817abf080a135da27cbc8faf4ddf60210b8/.github/workflows/courier_worker.yml): `workflow_dispatch`, a fixed task-type allow-list, dispatch-bound concurrency, and a dispatch-bound durable-result artifact. |
| GitHub reconciliation adapter | [`scripts/github_worker_adapter.py`](https://github.com/happyhippovip/2026-courier/blob/7004d817abf080a135da27cbc8faf4ddf60210b8/scripts/github_worker_adapter.py): dispatches that workflow, finds the exact dispatch run, downloads its named artifact, verifies it, and posts the result. |
| Exact identity/result schema | [`scripts/integration_contract.py`](https://github.com/happyhippovip/2026-courier/blob/7004d817abf080a135da27cbc8faf4ddf60210b8/scripts/integration_contract.py): task identity is `goal_id`, `task_id`, `attempt_id`, `dispatch_id`, and `worker_id`; a durable result requires those fields plus `run_id`, `result_id`, `status`, and `artifacts`, with numeric-string `run_attempt` required when supplied. Successful results require non-empty artifact entries exactly shaped as `path` and 64-character lowercase-hex `sha256`. |

Hosted evidence: [run `35092958584`](https://github.com/happyhippovip/2026-courier/actions/runs/35092958584) completed successfully for dispatch `test-auth-c5267df`; its [artifact `courier-result-test-auth-c5267df` (`10445300928`)](https://github.com/happyhippovip/2026-courier/actions/runs/35092958584/artifacts/10445300928) is available. [PR #30](https://github.com/happyhippovip/2026-courier/pull/30) merged as commit [`0efef85d25670b18f1b2c6f4420d85592d54cb3c`](https://github.com/happyhippovip/2026-courier/commit/0efef85d25670b18f1b2c6f4420d85592d54cb3c).
