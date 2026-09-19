SCALE_REVIEW=FAIL
FIRST_DEFECT=lock contention
INPUT_SIZE=concurrent workers
OBSERVED=conn.execute("BEGIN") in prefetch() creates a deferred transaction. Concurrent workers acquire SHARED locks and SELECT the same PENDING rows. When they try to UPDATE to ACTIVE, neither can upgrade to an EXCLUSIVE lock, resulting in a SQLITE_BUSY deadlock.
EXPECTED=prefetch() must use BEGIN IMMEDIATE to acquire the write lock atomically before SELECT, serializing claims and preventing lock contention.
HOT_PATH=scripts/magazine.py / prefetch
MINIMAL_FIX_SCOPE=Replace `conn.execute("BEGIN")` with `conn.execute("BEGIN IMMEDIATE")` in `MagazineLedger.prefetch()`.
