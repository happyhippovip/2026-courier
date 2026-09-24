import os
import shutil
import tempfile
import zipfile
import pytest

from scripts.update_courier import apply_update, get_current_version


def test_apply_update_success(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        app_dir = os.path.join(tmp_dir, "app")
        os.makedirs(app_dir)

        # Pre-existing file and version
        with open(os.path.join(app_dir, "version.txt"), "w", encoding="utf-8") as f:
            f.write("1.0.0\n")
        with open(os.path.join(app_dir, "existing.txt"), "w", encoding="utf-8") as f:
            f.write("keep-me\n")

        # Create update zip package
        update_zip = os.path.join(tmp_dir, "update.zip")
        with zipfile.ZipFile(update_zip, "w") as zf:
            zf.writestr("version.txt", "2.0.0\n")
            zf.writestr("new_feature.txt", "new-content\n")

        # Mock health_check to return True
        monkeypatch.setattr("scripts.update_courier.health_check", lambda path: True)

        apply_update(app_dir, update_zip, skip_restart=True)

        assert get_current_version(app_dir) == "2.0.0"
        assert os.path.exists(os.path.join(app_dir, "new_feature.txt"))
        assert os.path.exists(os.path.join(app_dir, "existing.txt"))


def test_apply_update_rollback_on_health_failure(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        app_dir = os.path.join(tmp_dir, "app")
        os.makedirs(app_dir)

        # Original state
        with open(os.path.join(app_dir, "version.txt"), "w", encoding="utf-8") as f:
            f.write("1.0.0\n")

        # Corrupt / bad update package
        update_zip = os.path.join(tmp_dir, "bad_update.zip")
        with zipfile.ZipFile(update_zip, "w") as zf:
            zf.writestr("version.txt", "2.0.0-bad\n")
            zf.writestr("bad_artifact.txt", "corrupt\n")

        # Mock health_check to fail
        monkeypatch.setattr("scripts.update_courier.health_check", lambda path: False)

        with pytest.raises(RuntimeError, match="Health check failed after update"):
            apply_update(app_dir, update_zip, skip_restart=True)

        # Check that rollback restored original version and removed new files
        assert get_current_version(app_dir) == "1.0.0"
        assert not os.path.exists(os.path.join(app_dir, "bad_artifact.txt"))
