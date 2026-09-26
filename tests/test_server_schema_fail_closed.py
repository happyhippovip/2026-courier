import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("COURIER_API_KEY", "test-key-12345")
os.environ.setdefault("COURIER_VERIFIER_API_KEY", "test-verifier-12345")

from server import app as server_app


def test_future_schema_fails_closed_with_system_exit(tmp_path, monkeypatch):
    """Unknown future schema_version must exit 1, not raise NameError."""
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"schema_version": 99}))
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))

    with pytest.raises(SystemExit) as exc:
        server_app.load_state()

    assert exc.value.code == 1
