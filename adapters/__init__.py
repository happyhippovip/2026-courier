"""V1 worker adapters (lane L4).

Each adapter module exposes the verifier entry point the controller calls::

    verify(task, result, home) -> Verdict-like

``task`` is a ``courier_core.state_machine.TaskState`` with status VERIFYING,
``result`` is the journaled ``RESULT_READY`` event, ``home`` is the
COURIER_HOME path the caller scopes file reads to. Adapter modules must never
write outside the work scope they are given and must never raise for malformed
input: a rejecting verdict is always returned instead.
"""
