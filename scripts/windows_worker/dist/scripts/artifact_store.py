"""Server-owned artifact store.

Workers upload the bytes of each artifact they produced; the server hashes the
bytes itself, stores them content-addressed and returns an immutable
artifact_id bound to the exact task/attempt/dispatch/worker and artifact name.
The verifier later reads the server-side copy and hashes it independently, so
it never opens a Mac/Windows local path and never trusts a worker-supplied
hash on its own.

Layout under the store root:
    blobs/<sha256[:2]>/<sha256>      artifact bytes (content-addressed)
    records/<artifact_id>.json       write-once binding record
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath

BINDING_FIELDS = ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id")
DEFAULT_MAX_BYTES = 16 * 1024 * 1024
ARTIFACT_ID_RE = re.compile(r"^art-[0-9a-f]{64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ArtifactError(ValueError):
    """Upload or reference rejected; the message never contains credentials."""


def is_safe_artifact_name(name) -> bool:
    """Workspace-relative names only: no absolute, drive, UNC or '..' paths."""
    if not isinstance(name, str) or not name or len(name) > 255 or "\x00" in name:
        return False
    for pure in (PureWindowsPath(name), PurePosixPath(name)):
        if pure.is_absolute() or pure.drive or pure.root or ".." in pure.parts:
            return False
    return True


def artifact_id_for(binding: dict, name: str, sha256: str) -> str:
    """Deterministic id: the same upload for the same dispatch is idempotent."""
    material = json.dumps(
        {"binding": {f: binding[f] for f in BINDING_FIELDS}, "name": name, "sha256": sha256},
        sort_keys=True, separators=(",", ":"),
    )
    return "art-" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class ArtifactStore:
    def __init__(self, root, max_bytes: int = DEFAULT_MAX_BYTES):
        self.root = Path(root)
        self.max_bytes = int(max_bytes)

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("COURIER_ARTIFACT_DIR", "server/state/artifacts"),
                   int(os.environ.get("COURIER_ARTIFACT_MAX_BYTES", DEFAULT_MAX_BYTES)))

    def _blob_path(self, sha256: str) -> Path:
        return self.root / "blobs" / sha256[:2] / sha256

    def _record_path(self, artifact_id: str) -> Path:
        if not ARTIFACT_ID_RE.match(artifact_id or ""):
            raise ArtifactError("invalid artifact_id")
        return self.root / "records" / f"{artifact_id}.json"

    def put(self, data: bytes, *, name: str, binding: dict, claimed_sha256: str | None = None,
            claimed_size: int | None = None) -> dict:
        if not is_safe_artifact_name(name):
            raise ArtifactError("unsafe artifact name")
        for field in BINDING_FIELDS:
            if not isinstance(binding.get(field), str) or not binding[field]:
                raise ArtifactError(f"missing binding field {field}")
        if len(data) > self.max_bytes:
            raise ArtifactError("artifact exceeds size limit")
        sha256 = hashlib.sha256(data).hexdigest()
        if claimed_sha256 is not None and claimed_sha256 != sha256:
            raise ArtifactError("uploaded bytes do not match the claimed sha256")
        if claimed_size is not None and claimed_size != len(data):
            raise ArtifactError("uploaded bytes do not match the claimed size")

        blob = self._blob_path(sha256)
        if blob.exists():
            if hashlib.sha256(blob.read_bytes()).hexdigest() != sha256:
                raise ArtifactError("stored blob is corrupt")
        else:
            _atomic_write(blob, data)

        artifact_id = artifact_id_for(binding, name, sha256)
        record = {"artifact_id": artifact_id, "name": name, "sha256": sha256, "size": len(data),
                  **{f: binding[f] for f in BINDING_FIELDS}}
        path = self._record_path(artifact_id)
        if path.exists():
            if json.loads(path.read_text(encoding="utf-8")) != record:
                raise ArtifactError("artifact record conflict")
        else:
            _atomic_write(path, json.dumps(record, sort_keys=True).encode("utf-8"))
        return record

    def get_record(self, artifact_id: str) -> dict | None:
        path = self._record_path(artifact_id)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def read_bytes(self, artifact_id: str) -> bytes:
        record = self.get_record(artifact_id)
        if record is None:
            raise ArtifactError("unknown artifact_id")
        blob = self._blob_path(record["sha256"])
        if not blob.is_file():
            raise ArtifactError("artifact bytes missing")
        return blob.read_bytes()

    def check_reference(self, ref: dict, task: dict) -> None:
        """Server-side check of a result's artifact reference against the task."""
        record = self.get_record(ref.get("artifact_id", ""))
        if record is None:
            raise ArtifactError("unknown artifact_id")
        for field in BINDING_FIELDS:
            if record[field] != task.get(field):
                raise ArtifactError(f"artifact {field} mismatch")
        if record["name"] != ref.get("path") or record["sha256"] != ref.get("sha256"):
            raise ArtifactError("artifact reference does not match stored record")
        if "size" in ref and record["size"] != ref["size"]:
            raise ArtifactError("artifact size mismatch")


def verify_uploaded_artifact(data: bytes, record: dict, ref: dict, task: dict) -> tuple[bool, str]:
    """Verifier-side: hash the server copy independently and check every binding."""
    actual = hashlib.sha256(data).hexdigest()
    if actual != ref.get("sha256") or actual != record.get("sha256"):
        return False, "hash mismatch"
    if len(data) != record.get("size") or ("size" in ref and ref["size"] != len(data)):
        return False, "size mismatch"
    if record.get("name") != ref.get("path") or record.get("artifact_id") != ref.get("artifact_id"):
        return False, "reference mismatch"
    for field in BINDING_FIELDS:
        if record.get(field) != task.get(field):
            return False, f"{field} mismatch"
    return True, "ok"


def create_blueprint(store: ArtifactStore, *, worker_auth, verifier_auth, task_lookup):
    """Flask routes: POST /artifacts (worker), GET /artifacts/<id>[/meta] (verifier).

    task_lookup(task_id) must return the current server task dict or None.
    """
    from flask import Blueprint, Response, jsonify, request

    bp = Blueprint("courier_artifacts", __name__)

    @bp.route("/artifacts", methods=["POST"])
    @worker_auth
    def upload_artifact():
        try:
            meta = json.loads(request.headers.get("X-Courier-Artifact", ""))
            if not isinstance(meta, dict):
                raise ValueError
        except ValueError:
            return jsonify({"error": "X-Courier-Artifact metadata header is required"}), 400
        length = request.content_length
        if length is None or length > store.max_bytes:
            return jsonify({"error": "artifact size missing or over limit"}), 413
        task = task_lookup(meta.get("task_id"))
        if not task or task.get("status") != "DISPATCHED":
            return jsonify({"error": "task is not awaiting artifacts"}), 409
        for field in BINDING_FIELDS:
            if meta.get(field) != task.get(field):
                return jsonify({"error": f"{field} mismatch"}), 400
        expected = [a.get("path") if isinstance(a, dict) else a for a in task.get("artifacts") or []]
        if meta.get("name") not in expected:
            return jsonify({"error": "artifact name is not expected by the task"}), 400
        data = request.get_data(cache=False)
        try:
            record = store.put(data, name=meta.get("name"), binding=task,
                               claimed_sha256=meta.get("sha256"), claimed_size=meta.get("size"))
        except ArtifactError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(record), 201

    @bp.route("/artifacts/<artifact_id>/meta", methods=["GET"])
    @verifier_auth
    def artifact_meta(artifact_id):
        try:
            record = store.get_record(artifact_id)
        except ArtifactError as exc:
            return jsonify({"error": str(exc)}), 400
        return (jsonify(record), 200) if record else (jsonify({"error": "unknown artifact"}), 404)

    @bp.route("/artifacts/<artifact_id>", methods=["GET"])
    @verifier_auth
    def artifact_bytes(artifact_id):
        try:
            data = store.read_bytes(artifact_id)
        except ArtifactError as exc:
            return jsonify({"error": str(exc)}), 404
        return Response(data, mimetype="application/octet-stream")

    return bp
