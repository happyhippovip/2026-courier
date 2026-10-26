"""Courier automation helpers (read-only journal export, CI watcher, RAID officer).

No engine, no scheduler, no network. ``raid_officer`` is a one-shot Event → Decision
function (``python -m tools.automation.raid_officer``). It does not write the ledger.
"""
