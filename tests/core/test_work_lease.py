import pytest
from courier_core.work_lease import (
    WorkLeaseManager, LeaseDeniedError, UnauthorizedReleaseError
)

def test_double_writer_rejected():
    mgr = WorkLeaseManager()
    mgr.acquire("integration/v1", "w1", "mac", "R01", ttl=60, now=100)
    
    with pytest.raises(LeaseDeniedError, match="is locked by writer 'w1'"):
        mgr.acquire("integration/v1", "w2", "mac", "R02", ttl=60, now=101)

def test_expired_lease_reclaimable():
    mgr = WorkLeaseManager()
    mgr.acquire("integration/v1", "w1", "mac", "R01", ttl=60, now=100)
    
    # At t=161, the lease is expired, w2 should be able to acquire
    lease = mgr.acquire("integration/v1", "w2", "mac", "R02", ttl=60, now=161)
    assert lease.writer == "w2"

def test_released_lease_reusable():
    mgr = WorkLeaseManager()
    mgr.acquire("integration/v1", "w1", "mac", "R01", ttl=60, now=100)
    mgr.release("integration/v1", "w1")
    
    # Immediately after release, w2 can acquire
    lease = mgr.acquire("integration/v1", "w2", "mac", "R02", ttl=60, now=101)
    assert lease.writer == "w2"

def test_wrong_owner_cannot_release():
    mgr = WorkLeaseManager()
    mgr.acquire("integration/v1", "w1", "mac", "R01", ttl=60, now=100)
    
    with pytest.raises(UnauthorizedReleaseError, match="Wrong owner cannot release lease"):
        mgr.release("integration/v1", "w2")

def test_read_only_work_unaffected():
    mgr = WorkLeaseManager()
    # Write lease acquired
    mgr.acquire("integration/v1", "w1", "mac", "R01", mode="WRITE", ttl=60, now=100)
    
    # Read leases can still be acquired by anyone
    read_lease_1 = mgr.acquire("integration/v1", "w2", "mac", "R02", mode="READ", ttl=60, now=101)
    assert read_lease_1.mode == "READ"
    assert read_lease_1.writer == "w2"
    
    read_lease_2 = mgr.acquire("integration/v1", "w3", "mac", "R03", mode="READ", ttl=60, now=102)
    assert read_lease_2.mode == "READ"
    assert read_lease_2.writer == "w3"

def test_heartbeat_extends_lease():
    mgr = WorkLeaseManager()
    mgr.acquire("integration/v1", "w1", "mac", "R01", ttl=60, now=100)
    mgr.heartbeat("integration/v1", "w1", ttl=60, now=150)
    
    # Now the expiry should be 210, so w2 cannot acquire at 160
    with pytest.raises(LeaseDeniedError):
        mgr.acquire("integration/v1", "w2", "mac", "R02", ttl=60, now=160)

def test_steal_recovery_rule():
    mgr = WorkLeaseManager()
    mgr.acquire("integration/v1", "w1", "mac", "R01", ttl=60, now=100)
    
    # Steal forceful takeover
    stolen = mgr.steal("integration/v1", "admin", "mac", "RECOVERY", ttl=60, now=110)
    assert stolen.writer == "admin"
    
    # Original writer can no longer heartbeat or release
    with pytest.raises(LeaseDeniedError):
        mgr.heartbeat("integration/v1", "w1", now=115)

