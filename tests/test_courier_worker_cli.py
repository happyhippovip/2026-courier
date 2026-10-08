"""Tests for the ``courier_worker.cli`` entry point wrapper (P9-worker-cli).

``courier_worker.cli:main`` is the ``courier-worker`` console script entry point.
It delegates to ``courier_worker.service.main(sys.argv)`` and returns its exit code.
Tests only; no behavior change.
"""

import sys
import courier_worker.cli as cli
import courier_worker.service as service


def test_wrapper_targets_service_main():
    assert cli._main is service.main
