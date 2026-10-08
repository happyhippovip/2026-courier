"""Dedicated tests for courier_worker.adapter_runner (P9 test hardening).

Covers the contained child process entrypoint executed by the worker host.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from courier_worker import adapter_runner


def test_adapter_runner_module_constants():
    assert "synthetic" in adapter_runner.ALLOWED
