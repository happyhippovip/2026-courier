"""O7-04: writer lease and ledger writer need a non-empty owner id (fail closed)."""
from __future__ import annotations

import pytest

from courier_core.controller import Controller
from courier_runtime.lease import LeaseStore
from courier_runtime.ledger_engine import LedgerEngine


@pytest.mark.parametrize("holder", [None, "", "   ", "\t\n"])
def test_o7_04_lease_without_owner_is_rejected(holder):
    store = LeaseStore(":memory:")
    try:
        with pytest.raises(ValueError):
            store.acquire("repo:test", holder, "WK-1", ttl_s=30)
    finally:
        store.close()


def test_o7_04_lease_with_owner_still_works():
    store = LeaseStore(":memory:")
    try:
        lease = store.acquire("repo:test", "host-a", "WK-1", ttl_s=30)
        assert lease.holder == "host-a"
    finally:
        store.close()


@pytest.mark.parametrize("host,writer", [("", None), ("host-a", ""), ("host-a", "   ")])
def test_o7_04_ledger_engine_rejects_empty_writer(tmp_path, host, writer):
    ctrl = Controller(tmp_path / "home", verifier=lambda adapter: None).boot()
    try:
        with pytest.raises(ValueError):
            LedgerEngine(ctrl, tmp_path / "campaign" / "kirby.json", host, writer_id=writer)
    finally:
        ctrl.stop()
