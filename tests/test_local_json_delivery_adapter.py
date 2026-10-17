import hashlib
import json
import os
import tempfile
import pytest
from pathlib import Path
from types import SimpleNamespace

from adapters.local_json_delivery import DeliveryError, run, verify
from courier_core.verification import adapter_verifier, run_verifier


def test_run_success():
    with tempfile.TemporaryDirectory() as td:
        params = {
            "article_id": "art-100",
            "title": "Bitcoin reaches milestone",
            "url": "https://example.com/art-100",
            "published_at": "2026-01-01T12:00:00Z",
        }
        res = run(params, td)
        assert res.outcome == "success"
        assert len(res.artifacts) == 1
        assert res.artifacts[0]["path"] == "art-100.json"

        target = Path(td) / "art-100.json"
        assert target.exists()

        data = target.read_bytes()
        assert hashlib.sha256(data).hexdigest() == res.artifacts[0]["sha256"]
        parsed = json.loads(data.decode("utf-8"))
        assert parsed["article_id"] == "art-100"
        assert parsed["title"] == "Bitcoin reaches milestone"


def test_run_invalid_params():
    with tempfile.TemporaryDirectory() as td:
        with pytest.raises(DeliveryError, match="missing article_id"):
            run({}, td)
        with pytest.raises(DeliveryError, match="unsafe file name"):
            run({"article_id": "../evil"}, td)


def test_verify_success():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        article_file = home / "art-200.json"
        content = json.dumps({"article_id": "art-200", "title": "Test Title"}).encode("utf-8")
        article_file.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()

        task = SimpleNamespace(
            dispatch_id="disp-1",
            effect_class="idempotent",
            params={"article_id": "art-200", "title": "Test Title"},
        )
        result = SimpleNamespace(
            dispatch_id="disp-1",
            payload={
                "outcome": "success",
                "artifacts": [{"path": "art-200.json", "sha256": digest}],
            },
        )

        verdict = verify(task, result, home)
        assert verdict.accepted is True
        assert "verified" in verdict.reason


def test_verify_dispatch_mismatch():
    with tempfile.TemporaryDirectory() as td:
        task = SimpleNamespace(dispatch_id="disp-1", effect_class="idempotent", params={"article_id": "art-1"})
        result = SimpleNamespace(
            dispatch_id="disp-2",
            payload={"outcome": "success", "artifacts": [{"path": "art-1.json", "sha256": "0" * 64}]},
        )
        verdict = verify(task, result, td)
        assert verdict.accepted is False
        assert "different dispatch" in verdict.reason


def test_verify_missing_file():
    with tempfile.TemporaryDirectory() as td:
        task = SimpleNamespace(dispatch_id="disp-1", effect_class="idempotent", params={"article_id": "art-1"})
        result = SimpleNamespace(
            dispatch_id="disp-1",
            payload={"outcome": "success", "artifacts": [{"path": "art-1.json", "sha256": "0" * 64}]},
        )
        verdict = verify(task, result, td)
        assert verdict.accepted is False
        assert "evidence file missing" in verdict.reason


def test_verify_hash_mismatch():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / "art-1.json").write_text('{"article_id": "art-1"}')
        task = SimpleNamespace(dispatch_id="disp-1", effect_class="idempotent", params={"article_id": "art-1"})
        result = SimpleNamespace(
            dispatch_id="disp-1",
            payload={"outcome": "success", "artifacts": [{"path": "art-1.json", "sha256": "0" * 64}]},
        )
        verdict = verify(task, result, td)
        assert verdict.accepted is False
        assert "hash does not match" in verdict.reason


def test_verify_content_mismatch():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        content = json.dumps({"article_id": "art-WRONG"}).encode("utf-8")
        (home / "art-1.json").write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()

        task = SimpleNamespace(dispatch_id="disp-1", effect_class="idempotent", params={"article_id": "art-1"})
        result = SimpleNamespace(
            dispatch_id="disp-1",
            payload={"outcome": "success", "artifacts": [{"path": "art-1.json", "sha256": digest}]},
        )
        verdict = verify(task, result, td)
        assert verdict.accepted is False
        assert "article_id does not match" in verdict.reason


def test_verify_path_traversal():
    with tempfile.TemporaryDirectory() as td:
        task = SimpleNamespace(dispatch_id="disp-1", effect_class="idempotent", params={"article_id": "art-1"})
        result = SimpleNamespace(
            dispatch_id="disp-1",
            payload={"outcome": "success", "artifacts": [{"path": "../art-1.json", "sha256": "0" * 64}]},
        )
        verdict = verify(task, result, td)
        assert verdict.accepted is False
        assert "escapes" in verdict.reason


def test_integration_with_run_verifier():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        content = json.dumps({"article_id": "art-500", "title": "Good News"}).encode("utf-8")
        (home / "art-500.json").write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()

        task = SimpleNamespace(
            adapter="local_json_delivery",
            dispatch_id="disp-500",
            effect_class="idempotent",
            params={"article_id": "art-500", "title": "Good News"},
        )
        result_event = SimpleNamespace(
            dispatch_id="disp-500",
            payload={
                "outcome": "success",
                "artifacts": [{"path": "art-500.json", "sha256": digest}],
            },
        )

        # Ensure adapter_verifier discovers local_json_delivery
        fn = adapter_verifier("local_json_delivery")
        assert fn is not None

        # Run through controller's canonical verifier gate
        verdict = run_verifier(adapter_verifier, task, result_event, home)
        assert verdict.accepted is True
        assert verdict.verifier is not None
        assert verdict.verifier["kind"] == "adapter"
        assert "adapters.local_json_delivery" in verdict.verifier["name"]
