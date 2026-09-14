import tempfile
from pathlib import Path

import pytest

from scripts.canonical_authority import CanonicalAuthority
from scripts.run_overnight_governor import (
    GOVERNOR_SCOPE,
    GOVERNOR_TASK_ID,
    acquire_governor_authority,
    main,
)


def test_governor_admission_is_single_flight_and_releasable():
    with tempfile.TemporaryDirectory(prefix="overnight-governor-") as tmp:
        workspace = Path(tmp)
        first, acquired, generation, error = acquire_governor_authority(
            workspace, "governor-one"
        )
        assert acquired is True
        assert error is None

        second, acquired_again, _, conflict = acquire_governor_authority(
            workspace, "governor-two"
        )
        assert acquired_again is False
        assert "is locked by" in conflict

        released, scopes = first.release_scopes(
            owner_id="governor-one",
            task_id=GOVERNOR_TASK_ID,
            scopes=[GOVERNOR_SCOPE],
            generation=generation,
        )
        assert released == 1
        assert scopes == [GOVERNOR_SCOPE]

        acquired_after_release, _, release_error = second.acquire_scopes(
            owner_id="governor-two",
            task_id=GOVERNOR_TASK_ID,
            scopes=[GOVERNOR_SCOPE],
            ttl_seconds=60,
        )
        assert acquired_after_release is True
        assert release_error is None


def test_governor_releases_authority_when_startup_fails(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="overnight-governor-failure-") as tmp:
        workspace = Path(tmp)
        monkeypatch.chdir(workspace)

        def fail_during_startup(*args, **kwargs):
            raise RuntimeError("DISPOSABLE_STARTUP_FAILURE")

        monkeypatch.setattr(
            "scripts.run_overnight_governor.FounderModeMVP",
            fail_during_startup,
        )

        with pytest.raises(RuntimeError, match="DISPOSABLE_STARTUP_FAILURE"):
            main()

        authority = CanonicalAuthority(locks_dir=workspace / "events" / "locks")
        assert GOVERNOR_SCOPE not in authority.list_active_locks()
