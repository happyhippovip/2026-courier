# Windows release handoff for L1

23 Oct 2026, Europe/Berlin. This file does not merge anything.

## Take these, separately

| PR | Branch | Head | Base | CI |
| --- | --- | --- | --- | --- |
| [#829](https://github.com/happyhippovip/2026-courier/pull/829) | `cursor/windows-lock-import-be3a` | `c954779416ac56530883836aa4d2fdbcc7b169fb` plus the continuity commit on top of it | `integration/v1` | [39955974009](https://github.com/happyhippovip/2026-courier/actions/runs/39955974009) success for `c95477941`. The continuity commit needs its own run. |
| [#828](https://github.com/happyhippovip/2026-courier/pull/828) | `cursor/windows-installer-rc-be3a` | `95463249f54c9d7ec46bbbc84cf466d710190849` | `integration/v1` | [39951521039](https://github.com/happyhippovip/2026-courier/actions/runs/39951521039) success. |

`integration/v1` was `d5b19f1dffe5f5478476bf090c522b38bfc7164e`. Both pull requests reported `MERGEABLE` and `CLEAN` against that base. They do not contain each other.

## Installer evidence, not rebuilt here

From the windows-build log of run `39951521039`, job `120406866483`, merge commit `780e247992555eb67a3a40b32d493454c54b008e`:

- `CourierSetup-v1.exe` SHA256 `C424171C842550E620BC98908FB9E9D71B4D2DB3D63D46530A757D425A1DE828`
- `CLEAN MACHINE` before the setup EXE
- silent install and Start menu shortcut
- silent upgrade
- silent uninstall

The hash belongs to that job. A later rebuild of `Courier.exe` changes it. Read that job's summary rather than an older matrix row.

## Do not take #827's copy of the worker

#827 head checked this session: `3fe68c1497625e75bb0786a921c88666b533ded9`. Its new commit does not touch the worker. A merge into #829 still conflicts only in:

- `scripts/windows_worker/daemon.py`
- `tests/test_windows_lock_fail_closed.py`

Keep #829's copies. #827's lock test stubbed `get_authority_store` to `None`. That is not a successful start. #826 and #830 were not edited.

## Worker rules already on #829

- Missing, stale, foreign, or `None` lease: exit 3. A dead pid from another host is not a local restart.
- `CLAIMED` may run once, and only after the file says `STARTED`.
- `STARTED` is not replayed. `RESULT_READY` is redelivered. `RELEASE_PENDING` releases and does not run again.
- One local workkey. A second home does not dispatch `WQ-1` while the first home holds it.
- Dead letter stays claimed. A second identical release is idempotent.
- `KILL` stops the next retry and does not release `FINAL`.

## Still not done

No Windows service, no Task Scheduler job, no logon autostart. The private checkpoint repository is HTTP 404. L1 merges. This branch does not.
