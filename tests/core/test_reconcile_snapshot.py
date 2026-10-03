from courier_core.mac_canonical_reconcile import CanonicalReconciler
from courier_core.snapshot_level_0 import SnapshotEngine

def test_canonical_reconciler():
    reconciler = CanonicalReconciler(["MAC-01", "MAC-02", "WK-10"])
    report = reconciler.reconcile_against_target(["MAC-01", "WK-10"])
    
    assert report["status"] == "CONTINUATION_MODE"
    assert len(report["missing"]) == 0
    
    report2 = reconciler.reconcile_against_target(["MAC-01", "MAC-99"])
    assert report2["status"] == "PENDING_RECONCILIATION"
    assert "MAC-99" in report2["missing"]

def test_snapshot_level_0():
    l0 = SnapshotEngine.capture_l0_state()
    assert l0.host_os == "macos"
    assert len(l0.active_process_ids) > 0
    assert 8080 in l0.open_ports
