# tests/automation RUNBOOK ([DRUIDE | ACCOUNT 2])

Scope: `tools/automation/journal_export.py` (WK-L6-JOURNAL-EXPORT) and `tools/automation/ci_watcher_v2.py` (WK-L6-CI-WATCHER-V2).
No network, no model calls, no secrets. The watcher tests use a stub `gh`; a real `gh` is never needed.

## Commands (from the repository root, Linux/macOS; on Windows use the same with `py -3`)
    export PYTHONDONTWRITEBYTECODE=1
    python3 -m pytest -p no:cacheprovider -q --no-header -rs tests/automation          # whole suite; check the exit code
    python3 -m pytest -p no:cacheprovider -q --no-header -rs tests/automation tests/test_github_worker_adapter.py tests/core/test_core_journal.py
    python3 tests/automation/ci_call_counts.py                                            # call-count harness, JSON, exit 0
    python3 -m pytest -p no:cacheprovider -q tests/automation/test_journal_export_round3.py tests/automation/test_journal_export_round4.py   # exporter last rounds
    python3 -m pytest -p no:cacheprovider -q tests/automation/test_ci_watcher_v2_round3.py                                              # watcher last round
Read the exit code (`echo $?`, or `${PIPESTATUS[0]}` behind a pipe), not only the last line. Every skip in `tests/automation` carries the reason prefix
`SKIPPED, NOT PASSED: ...`. Enforced at run time by `tests/automation/conftest.py` (a skip or xfail without the prefix, however it is spelled -
`from pytest import skip`, `importorskip`, `unittest.skip`, a reason-less `@pytest.mark.skip`, a module-level skip - turns into a FAILED test or a collection error;
checked by `test_round5_k0c.py::test_k0c_n4_*`). The AST scan `test_round5_k0.py::test_r3_2_every_skip_reason_starts_with_the_common_prefix` is only a lint of the
spelling `pytest.skip` / `pytest.mark.skip[if]` in the top folder of this directory. The conftest applies to runs that collect `tests/automation`; with `-rs` the skips are listed. The one skip outside this directory, `tests/test_github_worker_adapter.py` (needs flask), has no such prefix: it is not ours to change.
A skipped test proved nothing on that machine. Typical skips: chmod tests as root/Windows (the read-only-medium path is then covered by the forced-medium
tests `test_n_e5_*`), POSIX-only tests (directory fsync, flock) on Windows.

## Exit codes (checked against the code by `test_round5_k6.py`)
Exporter `python -m tools.automation.journal_export <db> [--out FILE] [--only-transitions] [--allow-partial] [--expect-head-hash HEX]`
| Exit | Meaning | What to do |
|---|---|---|
| 0 | exported | check `head_checked` in the header: false unless you gave `--expect-head-hash` |
| 2 | usage (bad flag, malformed hash, `--out` = the journal) | fix the command line; nothing was read |
| 3 | journal missing or unreadable (also: a database SQLite refuses to open) | check the path, permissions and that the file is a SQLite journal |
| 4 | hash chain broken, or stored text not valid UTF-8 | no export (with `--allow-partial` only the verified prefix); do not "repair" the journal, restore a copy and compare heads |
| 5 | event stream does not fold through the state machine | same as 4: a journal that is intact but inconsistent; escalate |
| 6 | output could not be written (disk full, broken pipe, bad `--out` dir) | fix the target, run again; the old `--out` file is untouched |
| 7 | journal changed while it was read (immutable read or snapshot lost) | run again; discard anything already read from stdout |
| 8 | head differs from `--expect-head-hash` (shorter, newer or replaced journal) | decide if the journal moved on legitimately; otherwise treat as truncation/tampering |

Watcher `python -m tools.automation.ci_watcher_v2 --workkey WK --sha <40 hex> --state-dir DIR ...` (one JSON line on stdout every time)
| Exit | Status | Meaning / what to do |
|---|---|---|
| 0 | SUCCESS (or RESET / NO_STATE for `--reset-state`) | all considered runs finished and succeeded (observer: after two identical finished looks; a clock set back between the two looks does not count: the next look starts over, so three looks are needed) |
| 1 | FINISHED_NOT_SUCCESS | runs finished, not all succeeded: read the runs in the JSON, look at GitHub |
| 2 | usage | numbers out of range/non-finite, `--dispatch-workflow` without `--ref`: nothing was written or called |
| 10 | WAITING | the window ended, the schedule is in the state file: run again (it does not poll before `next_poll_at`, except after a clock that jumped back: the wait is capped at `max_interval`) |
| 11 | EXHAUSTED | `max_attempts` used up: look at GitHub; to watch again `--reset-state` (keeps the dispatch marker) |
| 12 | DISPATCH_UNCONFIRMED | no run of ours showed up within `dispatch_grace`: see "DISPATCH_UNCONFIRMED" below; never dispatch again on your own |
| 13 | LOCKED | another watcher holds the key, or (O_EXCL lock) a takeover was interrupted or this watcher lost its lock: see "Stale lock" |
| 14 | STATE_UNREADABLE | state file damaged or belongs to another key: look at GitHub, then delete the dotfile by hand (a damaged state could hide a dispatch) |
| 15 | DISPATCH_AMBIGUOUS | the dispatch may have reached GitHub and is NOT repeated: check GitHub, then run again WITHOUT `--dispatch-workflow` |
| 16 | DISPATCH_FAILED | provably nothing was dispatched (gh could not start, HTTP 4xx, auth/usage error): the key is free, fix the cause, run again |
| 17 | IO_ERROR | state dir/state file/lock file not usable: fix permissions or space, run again |
| 18 | RESET_REFUSED | `--reset-state` only for COMPLETED/EXHAUSTED: look at GitHub, then delete the dotfile by hand |

## Restart (what a second call does)
* Same `--workkey`, `--sha` and `--state-dir` resume the state file: attempts, schedule and dispatch marker survive a crash, a reboot or a kill. A terminal state (COMPLETED, EXHAUSTED,
  DISPATCH_UNCONFIRMED) answers with zero gh calls. After SIGKILL no lock stays with flock; on the O_EXCL fallback the lock becomes stale after
  `max(600, 3*max_interval+300)` s and is taken over (see below).
* A killed watcher that had written the DISPATCHING marker never dispatches again for that key: it adopts the run if it shows up, otherwise ends DISPATCH_UNCONFIRMED.
* A new dispatch needs a new `--workkey`. Re-running a failed CI of the same commit: `--reset-state` (COMPLETED/EXHAUSTED only), then watch again.
* The exporter has nothing to restart: it is read-only and idempotent (same journal, same bytes). With `--out` a failed run leaves the previous file in place.

## Stale lock / dead taker (hand work, O_EXCL fallback only; with flock there is nothing to clean up)
1. Make sure no watcher for that key is running (`ps`), including on other machines that share the state dir.
2. (`<key>` is the 32-hex stem in the name of the state file `.ci-watch-<key>.json` of that workkey/SHA.) In the state dir delete `.ci-watch-<key>.lock.x` and every `.ci-watch-<key>.lock.x.take-*` (deleting only one of them also heals it).
3. Run the watcher again. A watcher that ends LOCKED with "lock lost" lost its lock to a taker while stalled: from the moment it noticed the loss (first heartbeat of a round, before the sleep) it dispatched, polled and wrote nothing; a poll that was already running when the takeover happened still finishes, its result is not written. Run it again later. If the loss happened while a dispatch had failed cleanly (DISPATCH_FAILED would be exit 16), the result is LOCKED (exit 13) instead and the state keeps the DISPATCHING marker although nothing was sent: the next run ends DISPATCH_UNCONFIRMED (exit 12, fail closed, never a second dispatch); look at GitHub, then delete the state dotfile by hand. A single failed read of the lock file (EACCES, EIO, EMFILE) counts as a loss, too: the watcher stops with exit 13 without writing the state, which is the safe direction and rare. `--reset-state` uses the largest stale limit (3 days + 300 s), so it never takes the lock of a living watcher; with a lock left by a crash it ends LOCKED (exit 13): clean up by hand as above.

## DISPATCH_UNCONFIRMED (exit 12)
Check on GitHub whether the run exists. If the local clock runs more than 5 s ahead of GitHub's, fix it (NTP). `--reset-state` does not help here (exit 18, RESET_REFUSED). Delete the state dotfile by hand and run again WITHOUT
`--dispatch-workflow` (observer mode); running with `--dispatch-workflow` would send a new dispatch.

## Rollback (undoing this change set)
The tools are stand-alone and nothing else imports them (UNKNOWN for code outside this repository). To go back: `git revert` the commits of branch `acc2/automation-v2-fixes`
(or check out the previous tag/commit of `tools/automation/` and `tests/automation/`), never a force-push. The state files of the watcher are plain JSON
(`.ci-watch-*.json`) and stay valid across versions as long as `key`, `sha`, `dispatch` and `dispatched_at` are kept: delete them only after looking at GitHub, because the dispatch marker is
what prevents a second dispatch. The exporter writes nothing to the journal, so rolling it back has no data effect; delete exported files by hand if you want them gone.

## Edge-case coverage (where each class is tested; `file::test`)
| Class | Exporter (`test_journal_export*.py`) | Watcher (`test_ci_watcher_v2*.py`) |
|---|---|---|
| malformed input | `test_usage_error_exits_2`, `test_n_e3_a_malformed_head_hash_is_a_usage_error_not_a_head_mismatch`, `test_directory_empty_file_and_garbage_are_exit_3`, `test_invalid_utf8_*` | `test_n_w4_non_finite_flags_are_a_usage_error_before_any_gh_call`, `test_n_3_the_library_enforces_the_same_bounds_as_the_cli`, `test_cli_rejects_negative_or_nonsense_numbers`, `test_badly_typed_state_fields_are_unreadable_not_a_crash` |
| races / live writer | `test_concurrent_writer_every_export_is_a_consistent_snapshot`, `test_n_e4_pass_2_reads_the_snapshot_of_pass_1_even_if_the_journal_is_rewritten_in_between`, `test_ex3_writer_starting_while_the_output_pipe_is_blocked_cannot_truncate_the_export` | `test_n_w1_two_takers_of_one_stale_lock_never_both_hold_it`, `test_n_w1_the_same_race_the_other_way_round_and_three_takers` |
| stale locks | — | `test_cw5_*`, `test_n_w1_a_takeover_that_died_midway_fails_closed_and_the_locked_result_names_the_files`, `test_n_w1_release_does_not_remove_a_lock_somebody_else_took_over`, `test_n_w5_the_watch_loop_refreshes_the_heartbeat_before_and_after_every_sleep` |
| interrupted export / write | `test_interrupt_while_writing_leaves_no_tmp_file_and_no_half_output`, `test_ex3_changed_journal_with_out_never_replaces_the_previous_export`, `test_unwritable_out_path_exits_6_after_a_good_read`, `test_broken_pipe_on_stdout_is_exit_6_and_journal_untouched`, `test_n_r4_out_fsyncs_the_directory_after_the_rename` | `test_t1_*` (atomic state write), `test_n_w5_write_state_fsyncs_the_directory_after_the_replace` |
| re-execution | `test_repeated_export_is_byte_identical_and_stdout_equals_out_file` | `S5_already_posted` in `ci_call_counts.py`, `test_cw3_*` (`--reset-state`), no second dispatch after an ambiguous dispatch (`test_cw6_*`) |
| tampering / truncation | `test_broken_chain_exits_4_and_exports_nothing_by_default`, `test_b3_expect_head_hash_detects_the_cut_off_tail_with_exit_8`, `test_truncated_*` | — |
| stability window (observer) | — | `test_n_2_two_finished_looks_hours_apart_are_not_a_confirmation`, `test_r3_w5_two_looks_up_to_3_max_interval_plus_60_seconds_apart_confirm`, `test_k7_c06_a_clock_that_went_back_between_two_finished_looks_is_not_a_confirmation` (clock set back: no confirmation) (boundary 75 s / 75.5 s for max_interval 5) |
| absurd but finite numbers | — | `test_r3_w1_*` (CLI exit 2, library ValueError, `Backoff.delay` never overflows) |
| lock lost / future mtime | — | `test_r3_w2_*`, `test_r3_w3_*`, `test_k0c_n1_*` (lost before dispatch, during dispatch, during poll), `test_k0c_n3_*` (mtime thresholds, 600 s floor) |
| check order | `test_r3_e2_*` (usage error before a missing journal) | — |

Test-name patterns with `*` stand for several tests; list them with `pytest --collect-only -q tests/automation | grep <pattern>`.

## Known limits (not tested, do not read as proven)
Real GitHub, NFS, and Windows execution of the lock fallback (UNKNOWN; the Windows RUNBOOK commands are untested, too).

Lock remainders of the O_EXCL fallback (platforms without `fcntl`; with flock none of this exists):
* A taker killed inside the takeover window leaves `<state>.lock.x` and `<state>.lock.x.take-<inode>-<mtime_ns>`. This fails closed on purpose:
  every watcher of that key then ends LOCKED (exit 13) until you delete BOTH files by hand in the state dir (deleting only one also heals it).
  Check first that no watcher for that key is running. The design is kept: an automatic clean-up of the guard could let two takers act at once.
* Residual races of the heartbeat (the owner is stalled between "re-check" and "unlink", or a takeover happens right after the owner's last check) cannot be closed
  without a kernel lock. The owner checks that the lock is still its own (heartbeat) before the sleep, after the sleep, before the dispatch and before every state write, and ends with
LOCKED ("lock lost") without dispatching, polling or writing once the check fails. What stays open: the time between that check and the write (or the
`gh` call that already started: a poll or dispatch in flight when the takeover happens still completes, its result is simply not written). A dispatch that was
already sent when the lock was lost leaves the DISPATCHING marker in the state file, so nobody dispatches the key a second time. Only the O_EXCL fallback has this
(flock needs no takeover).
* A lock file whose mtime lies far in the future (clock set back by more than the stale limit) counts as stale; a slightly future mtime counts as live.
  Known limit (Schurke K0-2, not fixed): the age of the lock is compared with the wall clock, because the lock file is shared between processes and no
  monotonic clock is shared. If the clock of a TAKER jumps back by more than the stale limit (at least 600 s), a lock that is alive counts as stale and two processes
  hold it until the owner's next heartbeat (before and after every sleep, before every state write), where the owner sees the loss and stops; a poll already running
  at that moment (gh timeout 120 s) still finishes, its result is not written. Keep the clock on NTP; with flock (Linux, macOS) this cannot happen.

Extreme values: `--base/--max-interval/--window` are limited to 86400 s, `--factor` to 100 (exit 2 beyond that, library: ValueError); the exponential delay is
computed without overflow for any number of attempts. `--max-attempts 0 --window 0` runs until a terminal state and can therefore run for a very long time on purpose.

Observer after a manual reset from DISPATCH_UNCONFIRMED (R3-W6): the observer counts ALL runs of the SHA, so an older red run gives FINISHED_NOT_SUCCESS.
That is NOT a guarantee against a false SUCCESS: if every run of the SHA is green, including a run of ANOTHER workflow of the same SHA, the observer reports SUCCESS
(after two identical finished looks). In observer mode SUCCESS means "all runs of this SHA that GitHub lists are green", not "the run you meant". `--reset-state`
from DISPATCH_UNCONFIRMED is refused (exit 18, RESET_REFUSED); the only way out is deleting the state dotfile by hand after looking at GitHub.

Very small `--window`: a poll that is due right now is always made once per call (it costs no waiting), so even `--window 1e-9` looks once and then ends WAITING (exit 10)
with 1 poll. (Before K0d a window shorter than the clock tick gave exit 10 with 0 polls.) A window of 0 means no limit.

Order of checks in the exporter: a malformed `--expect-head-hash` is exit 2 first, even if the journal is missing. Then the journal is resolved: missing = exit 3
(also when `--out` names that same path), `--out` = an existing journal or one of its sidecars = exit 2, broken = 4.
