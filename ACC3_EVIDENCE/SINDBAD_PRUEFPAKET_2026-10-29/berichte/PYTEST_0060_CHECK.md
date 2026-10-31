# WK-PRUEFER-012 Vertretung – PYTEST_0060-Logs (29.10.2026 19:00 MEZ)
"3 passed, EXIT 0" ist nur der letzte Block (tests/test_gate2_two_workkeys.py). In beiden Logs gibt es einen roten Block:
- PYTEST_0060_9afe8706.log: tests/hub → 3 failed, 145 passed, EXIT 1 (18:54:24), u. a. test_kolibri_view.py::test_github_payload_is_shown_and_a_failed_read_is_unknown
- PYTEST_0060_a209b3fe.log: tests/hub → 15 failed, 128 passed, EXIT 1 (18:52:14), u. a. test_hub_product.py::test_a_recorded_decision_is_never_reported_as_failed_when_the_reread_breaks
Übrige Blöcke grün (u. a. 220 passed/1 skipped). Akzeptanz "pytest nachgelaufen, alle OK" NICHT erfüllt → WK-012 ROT.
