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
Read the exit code (`echo $?`, or `${PIPESTATUS[0]}` behind a pipe), not only the last line. Skips print as `SKIPPED, NOT PASSED: ...` with `-rs`
(chmod tests as root/Windows; directory-fsync tests on Windows; the adapter test needs flask).

## Edge-case coverage (where each class is tested; `file::test`)
| Class | Exporter (`test_journal_export*.py`) | Watcher (`test_ci_watcher_v2*.py`) |
|---|---|---|
| malformed input | `test_usage_error_exits_2`, `test_n_e3_a_malformed_head_hash_is_a_usage_error_not_a_head_mismatch`, `test_directory_empty_file_and_garbage_are_exit_3`, `test_invalid_utf8_*` | `test_n_w4_non_finite_flags_are_a_usage_error_before_any_gh_call`, `test_n_3_the_library_enforces_the_same_bounds_as_the_cli`, `test_cli_rejects_negative_or_nonsense_numbers`, `test_badly_typed_state_fields_are_unreadable_not_a_crash` |
| races / live writer | `test_concurrent_writer_every_export_is_a_consistent_snapshot`, `test_n_e4_pass_2_reads_the_snapshot_of_pass_1_even_if_the_journal_is_rewritten_in_between`, `test_ex3_writer_starting_while_the_output_pipe_is_blocked_cannot_truncate_the_export` | `test_n_w1_two_takers_of_one_stale_lock_never_both_hold_it`, `test_n_w1_the_same_race_the_other_way_round_and_three_takers` |
| stale locks | — | `test_cw5_*`, `test_n_w1_a_takeover_that_died_midway_fails_closed_and_the_locked_result_names_the_files`, `test_n_w1_release_does_not_remove_a_lock_somebody_else_took_over`, `test_n_w5_the_watch_loop_refreshes_the_heartbeat_before_and_after_every_sleep` |
| interrupted export / write | `test_interrupt_while_writing_leaves_no_tmp_file_and_no_half_output`, `test_ex3_changed_journal_with_out_never_replaces_the_previous_export`, `test_unwritable_out_path_exits_6_after_a_good_read`, `test_broken_pipe_on_stdout_is_exit_6_and_journal_untouched`, `test_n_r4_out_fsyncs_the_directory_after_the_rename` | `test_t1_*` (atomic state write), `test_n_w5_write_state_fsyncs_the_directory_after_the_replace` |
| re-execution | `test_repeated_export_is_byte_identical_and_stdout_equals_out_file` | `S5_already_posted` in `ci_call_counts.py`, `test_cw3_*` (`--reset-state`), no second dispatch after an ambiguous dispatch (`test_cw6_*`) |
| tampering / truncation | `test_broken_chain_exits_4_and_exports_nothing_by_default`, `test_b3_expect_head_hash_detects_the_cut_off_tail_with_exit_8`, `test_truncated_*` | `test_n_2_two_finished_looks_hours_apart_are_not_a_confirmation` |

Test-name patterns with `*` stand for several tests; list them with `pytest --collect-only -q tests/automation | grep <pattern>`.

## Known limits (not tested, do not read as proven)
Real GitHub, NFS, Windows execution of the lock fallback, and a taker killed inside the takeover window (that case fails closed, exit 13).
