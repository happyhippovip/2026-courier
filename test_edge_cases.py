from scripts.scope_ledger import ScopeLedger
import os

ledger = ScopeLedger("test_edge.sqlite3")
l1 = ledger.acquire_lease("/FOO/bar", "WRITE", "t1", "e1", "w1")
l2 = ledger.acquire_lease("/foo/bar", "WRITE", "t2", "e2", "w2")

print("l1:", l1 is not None)
print("l2:", l2 is not None)
