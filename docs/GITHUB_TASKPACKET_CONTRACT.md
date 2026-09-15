# GitHub bounded TaskPacket contract

`.github/workflows/courier-taskpacket.yml` is the generic GitHub execution
boundary for Courier. It is independent of Revenue V1 and does not invoke
OpenAI, local workers, coordinator code, or arbitrary task payloads.

## Dispatch interface

Dispatch the workflow with all four stable Courier identities and the only
supported operation:

```sh
gh workflow run courier-taskpacket.yml \
  --ref <immutable-or-reviewed-ref> \
  -f task_id=<task-id> \
  -f attempt_id=<attempt-id> \
  -f dispatch_id=<dispatch-id> \
  -f result_id=<result-id> \
  -f operation=repository-metadata-v1
```

The workflow constructs a schema-bound TaskPacket with those identities plus
the immutable GitHub `run_id`, `run_attempt`, repository, ref, and SHA. The
only operation returns that already-provided repository metadata. It checks
out only this contract implementation with persisted credentials disabled and
receives no repository write, pull-request, issue, or token permissions.
Each identity is a 1-64 character ASCII value matching
`[A-Za-z0-9][A-Za-z0-9._-]*`; this also keeps the artifact name within the
GitHub Actions limit.

## Exact result retrieval

Courier must retain the `run_id` returned by GitHub dispatch discovery and
retrieve only that run; it must never query a latest run. Download the
run-scoped artifact and verify every supplied identity before accepting it:

```sh
gh run download <run-id> \
  --name courier-taskpacket-verified-result-<task-id>-<attempt-id>-<dispatch-id> \
  --dir <destination>
```

The artifact contains `result.json`, governed by
`schemas/github_task_result.schema.json`, and `verification.json` from the
separate `github-actions-taskpacket-verifier-v1` job. The terminal result has
`status` of `SUCCEEDED` or `REJECTED`, carries `task_id`, `attempt_id`,
`dispatch_id`, `result_id`, `github_run_id`, and `github_run_attempt`, and
must match the retained dispatch identities exactly. Rejected packets still
produce this artifact; the workflow run then fails visibly. Results are kept
for 14 days, and no workflow writes repository content or bypasses human
review.
