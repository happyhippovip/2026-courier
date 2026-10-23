import pytest

from courier_runtime.lease import LeaseConflict, LeaseStore, StaleLease


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


# -- work lease ---------------------------------------------------------------

@pytest.fixture
def leases(tmp_path):
    clock = Clock()
    store = LeaseStore(str(tmp_path / "lease.db"), clock=clock)
    yield store, clock
    store.close()


def test_one_active_write_lease_per_scope(leases):
    store, _ = leases
    first = store.acquire("repo:integration/v1", "mac:s1", "wk-1", ttl_s=30)
    with pytest.raises(LeaseConflict):
        store.acquire("repo:integration/v1", "win:s2", "wk-2", ttl_s=30)
    other = store.acquire("repo:other", "win:s2", "wk-2", ttl_s=30)
    assert other.token != first.token
    assert other.token > first.token


def test_expired_lease_can_be_taken_over_and_old_holder_is_fenced(leases):
    store, clock = leases
    old = store.acquire("scope", "mac:s1", "wk-1", ttl_s=30)
    clock.t += 31
    new = store.acquire("scope", "win:s2", "wk-1", ttl_s=30)
    assert new.token == old.token + 1
    with pytest.raises(StaleLease):
        store.check_write("scope", old.token)       # a still-running old holder cannot write
    with pytest.raises(StaleLease):
        store.renew(old, ttl_s=30)                  # nor heartbeat its way back
    assert store.check_write("scope", new.token).holder == "win:s2"


def test_heartbeat_extends_and_same_holder_reacquire_keeps_token(leases):
    store, clock = leases
    lease = store.acquire("scope", "h", "wk", ttl_s=10)
    clock.t += 8
    lease = store.renew(lease, ttl_s=10)
    clock.t += 8
    assert store.current("scope") is not None
    assert store.acquire("scope", "h", "wk", ttl_s=10).token == lease.token


def test_same_holder_different_workkey_conflicts_while_lease_is_live(leases):
    # Issue #188 F12: Workspace uses host.device_id as holder, so two workkeys on one
    # device used to share the scope AND the fencing token; both writers passed check_write.
    store, _ = leases
    first = store.acquire("scope", "mac", "wk-A", ttl_s=30)
    with pytest.raises(LeaseConflict):
        store.acquire("scope", "mac", "wk-B", ttl_s=30)
    assert store.check_write("scope", first.token).workkey == "wk-A"


def test_same_holder_new_workkey_after_expiry_gets_new_token_and_fences_old(leases):
    store, clock = leases
    old = store.acquire("scope", "mac", "wk-A", ttl_s=30)
    clock.t += 31
    new = store.acquire("scope", "mac", "wk-B", ttl_s=30)
    assert new.token == old.token + 1
    with pytest.raises(StaleLease):
        store.check_write("scope", old.token)


def test_release_frees_scope_but_token_keeps_increasing(leases):
    store, _ = leases
    first = store.acquire("scope", "a", "wk", ttl_s=10)
    store.release(first)
    assert store.current("scope") is None
    assert store.acquire("scope", "b", "wk", ttl_s=10).token == first.token + 1


def test_two_connections_see_the_same_lease(tmp_path):
    clock = Clock()
    a = LeaseStore(str(tmp_path / "l.db"), clock=clock)
    b = LeaseStore(str(tmp_path / "l.db"), clock=clock)
    a.acquire("scope", "a", "wk", ttl_s=10)
    with pytest.raises(LeaseConflict):
        b.acquire("scope", "b", "wk", ttl_s=10)
    a.close()
    b.close()


def test_hierarchical_scope_overlap_raises_conflict(leases):
    store, _ = leases
    # Parent scope acquired by Holder 1
    store.acquire("repo://courier_hub/static", "holder-1", "wk-parent", ttl_s=30)

    # Child scope attempted by Holder 2 -> LeaseConflict
    with pytest.raises(LeaseConflict):
        store.acquire("repo://courier_hub/static/evidence_badge.mjs", "holder-2", "wk-child", ttl_s=30)

    # Different subpath attempted by different workkey on same holder -> LeaseConflict
    with pytest.raises(LeaseConflict):
        store.acquire("repo://courier_hub/static/kolibri.html", "holder-1", "wk-diff", ttl_s=30)


def test_child_scope_blocks_parent_scope_acquisition(leases):
    store, _ = leases
    # Child scope acquired first
    store.acquire("repo://courier_hub/static/evidence_badge.mjs", "holder-1", "wk-child", ttl_s=30)

    # Parent scope attempted by another holder -> LeaseConflict
    with pytest.raises(LeaseConflict):
        store.acquire("repo://courier_hub/static", "holder-2", "wk-parent", ttl_s=30)


def test_scope_canonicalization_normalizes_paths(leases):
    from courier_runtime.lease import canonicalize_scope, scopes_overlap

    assert canonicalize_scope("repo://courier_hub//static/") == "repo://courier_hub/static"
    assert canonicalize_scope("path//to/dir/") == "path/to/dir"
    assert scopes_overlap("repo://courier_hub/static", "repo://courier_hub/static/evidence_badge.mjs")
    assert scopes_overlap("repo://courier_hub/static/evidence_badge.mjs", "repo://courier_hub/static")
    assert not scopes_overlap("repo://courier_hub/static", "repo://courier_core/journal.py")


def test_session_holder_binding_and_parse():
    from courier_runtime.lease import format_session_holder, parse_session_holder

    formatted = format_session_holder("mac-01", 1234, 17924500.1234, "sess-abc")
    parsed = parse_session_holder(formatted)
    assert parsed is not None
    assert parsed["device"] == "mac-01"
    assert parsed["pid"] == 1234
    assert parsed["session_id"] == "sess-abc"
    assert parse_session_holder("plain-string") is None


def test_fenced_file_writer_prevents_unauthorized_writes(leases, tmp_path):
    from courier_runtime.lease import FencedFileWriter

    store, clock = leases
    lease = store.acquire("repo://docs", "writer-1", "wk-doc", ttl_s=10)
    target_file = tmp_path / "test.txt"

    # Fenced writer with valid token succeeds
    writer = FencedFileWriter(store, "repo://docs", lease.token)
    with writer.open(target_file, "w") as f:
        f.write("hello guarded world")
    assert target_file.read_text() == "hello guarded world"

    # Fenced writer with stale token raises StaleLease
    stale_writer = FencedFileWriter(store, "repo://docs", lease.token + 99)
    with pytest.raises(StaleLease):
        stale_writer.open(target_file, "w")

    # When lease expires, write is refused
    clock.t += 15
    with pytest.raises(StaleLease):
        writer.open(target_file, "w")


def test_lease_store_refuses_a_symlinked_parent(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "home"
    link.symlink_to(outside, target_is_directory=True)
    try:
        store = LeaseStore(str(link / "agents.db"))
    except OSError as exc:
        assert "symlink" in str(exc).lower()
    else:
        store.close()
        raise AssertionError(sorted(path.name for path in outside.iterdir()))
    assert list(outside.iterdir()) == []


def test_lease_store_refuses_a_symlink_and_leaves_the_target_empty(tmp_path):
    target = tmp_path / "target.db"
    target.write_bytes(b"")
    link = tmp_path / "agents.db"
    link.symlink_to(target)
    try:
        store = LeaseStore(str(link))
    except OSError as exc:
        assert "symlink" in str(exc).lower()
    else:
        store.close()
        raise AssertionError(f"opened a symlinked lease db, target size {target.stat().st_size}")
    assert target.read_bytes() == b""


def test_fenced_writer_refuses_a_symlinked_parent(leases, tmp_path):
    from courier_runtime.lease import FencedFileWriter

    store, _ = leases
    lease = store.acquire("repo://docs", "writer-1", "wk-doc", ttl_s=10)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "linked"
    link.symlink_to(outside, target_is_directory=True)
    writer = FencedFileWriter(store, "repo://docs", lease.token, "writer-1")
    with pytest.raises(OSError, match="symlink"):
        with writer.open(link / "report.txt", "w") as handle:
            handle.write("nope")
    assert list(outside.iterdir()) == []


def test_fenced_writer_refuses_a_symlink_and_leaves_the_target(leases, tmp_path):
    from courier_runtime.lease import FencedFileWriter

    store, _ = leases
    lease = store.acquire("repo://docs", "writer-1", "wk-doc", ttl_s=10)
    secret = tmp_path / "secret.txt"
    secret.write_text("keep", encoding="utf-8")
    link = tmp_path / "report.txt"
    link.symlink_to(secret)
    writer = FencedFileWriter(store, "repo://docs", lease.token, "writer-1")
    with pytest.raises(OSError, match="symlink"):
        with writer.open(link, "w") as handle:
            handle.write("replaced")
    assert secret.read_text(encoding="utf-8") == "keep"


def test_enclosing_parent_scope_authorizes_child_path_write(leases):
    store, _ = leases
    lease = store.acquire("repo://courier_hub/static", "writer-1", "wk-hub", ttl_s=30)
    # Child path write check with parent token passes
    checked = store.check_write("repo://courier_hub/static/evidence_badge.mjs", lease.token)
    assert checked.token == lease.token


def test_check_write_verifies_holder_and_workkey(leases):
    store, _ = leases
    lease = store.acquire("repo://docs", "writer-1", "wk-doc", ttl_s=30)

    # Valid holder and workkey pass
    checked = store.check_write("repo://docs", lease.token, holder="writer-1", workkey="wk-doc")
    assert checked.holder == "writer-1"
    assert checked.workkey == "wk-doc"

    # Mismatched holder raises StaleLease
    with pytest.raises(StaleLease):
        store.check_write("repo://docs", lease.token, holder="foreign-writer", workkey="wk-doc")

    # Mismatched workkey raises StaleLease
    with pytest.raises(StaleLease):
        store.check_write("repo://docs", lease.token, holder="writer-1", workkey="wrong-workkey")


def test_child_scope_lease_does_not_authorize_parent_scope_write(leases):
    store, _ = leases
    # Acquire lease strictly on a child file/subdirectory
    child_lease = store.acquire("repo://courier_hub/static/evidence_badge.mjs", "writer-child", "wk-child", ttl_s=30)

    # Writing to child path succeeds
    checked = store.check_write("repo://courier_hub/static/evidence_badge.mjs", child_lease.token)
    assert checked.token == child_lease.token

    # Writing to parent scope MUST be refused (scopes_overlap must NOT elevate child lease to parent)
    with pytest.raises(StaleLease):
        store.check_write("repo://courier_hub/static", child_lease.token)

    # Writing to root scope MUST be refused
    with pytest.raises(StaleLease):
        store.check_write("repo://courier_hub", child_lease.token)

