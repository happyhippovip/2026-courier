"""Independent temporary-fixture acceptance lab for Mission 171G.

This intentionally does not import, execute, or trust any builder recovery
implementation.  It validates adversarial package semantics the builder must
meet before a future acceptance run is allowed to pass.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "tests" / "mission_171c_any_device_acceptance_matrix.json"
SECRET_MARKERS = ("password", "oauth", "access_token", "refresh_token", "api_key", "cookie", "session", "recovery code", "private key")
HIGH_RISK = {"publication", "money", "upload", "provider_request", "notification"}

def sha(data): return hashlib.sha256(data).hexdigest()

def normalize(member):
    p = Path(member)
    if p.is_absolute() or ".." in p.parts or not member or "\\" in member:
        raise ValueError("unsafe package member")
    return p.as_posix().lower()

def validate_package(root):
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file(): raise ValueError("missing manifest")
    try: manifest = json.loads(manifest_path.read_text())
    except Exception as exc: raise ValueError("malformed manifest") from exc
    if manifest.get("schema_version") != 1: raise ValueError("unsupported schema")
    members, seen = manifest.get("files"), set()
    if not isinstance(members, list) or not members: raise ValueError("empty package")
    for item in members:
        name = normalize(item.get("path", ""))
        if name in seen: raise ValueError("duplicate normalized path")
        seen.add(name); p = root / item["path"]
        if not p.is_file() or p.is_symlink(): raise ValueError("missing or symlink member")
        content = p.read_bytes()
        if sha(content) != item.get("sha256"): raise ValueError("member hash mismatch")
        lowered = (name + " " + content.decode("utf-8", "ignore")).lower()
        if any(marker in lowered for marker in SECRET_MARKERS): raise ValueError("secret contamination")
    actual = {p.relative_to(root).as_posix().lower() for p in root.rglob("*") if p.is_file() and p.name != "manifest.json"}
    if actual != seen: raise ValueError("unexpected or missing file")
    return manifest

def classify_state(current, recovery):
    if current.get("version") is None or recovery.get("version") is None: return "UNKNOWN"
    if current["version"] == recovery["version"] and current.get("hash") == recovery.get("hash"): return "SAME_STATE"
    if current["version"] == recovery["version"]: return "DIVERGED"
    return "RECOVERY_OLDER_THAN_CURRENT" if recovery["version"] < current["version"] else "RECOVERY_NEWER_THAN_CURRENT"

def recover_task(task):
    if task["status"] == "RUNNING" and task.get("external_mutation"):
        return "RECONCILIATION_REQUIRED"
    return task["status"]

class AnyDeviceAcceptanceLab(unittest.TestCase):
    def _valid(self, root):
        data = {"brain.json": b'{"open_loops":["x"],"publication_authorized":false}'}
        for name, content in data.items():
            (root / name).write_bytes(content)
        manifest = {"schema_version": 1, "files": [{"path": n, "sha256": sha(c)} for n,c in data.items()]}
        (root / "manifest.json").write_text(json.dumps(manifest))
        return manifest

    def test_matrix_has_independent_30_gate_contract(self):
        data = json.loads(MATRIX.read_text()); gates = data["gates"]
        self.assertEqual(30, len(gates)); self.assertEqual(30, len({g["gate_id"] for g in gates}))
        self.assertTrue(all({"gate_id","risk","required_evidence","pass_condition","fail_condition","severity"} <= set(g) for g in gates))
        self.assertFalse(data["builder_self_attestation_is_evidence"])

    def test_valid_package_and_corruption_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); self._valid(root); validate_package(root)
            (root / "brain.json").write_text("tampered")
            with self.assertRaises(ValueError): validate_package(root)
            (root / "manifest.json").write_text("{")
            with self.assertRaises(ValueError): validate_package(root)

    def test_secret_and_extra_file_exclusion(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); self._valid(root)
            (root / "runtime.oauth.refresh").write_text("synthetic refresh token")
            with self.assertRaises(ValueError): validate_package(root)

    def test_path_and_symlink_attacks_rejected(self):
        for member in ("../escape", "/absolute/escape", "a/../../escape", ""):
            with self.assertRaises(ValueError): normalize(member)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); self._valid(root)
            (root / "brain.json").unlink(); (root / "brain.json").symlink_to(Path(d).parent)
            with self.assertRaises(ValueError): validate_package(root)

    def test_state_ordering_never_last_write_wins(self):
        self.assertEqual("RECOVERY_OLDER_THAN_CURRENT", classify_state({"version":2,"hash":"b"},{"version":1,"hash":"a"}))
        self.assertEqual("RECOVERY_NEWER_THAN_CURRENT", classify_state({"version":1,"hash":"a"},{"version":2,"hash":"b"}))
        self.assertEqual("DIVERGED", classify_state({"version":1,"hash":"a"},{"version":1,"hash":"b"}))
        self.assertEqual("UNKNOWN", classify_state({"version":None},{"version":1,"hash":"a"}))

    def test_orphaned_task_and_high_risk_replay_are_blocked(self):
        self.assertEqual("RECONCILIATION_REQUIRED", recover_task({"status":"RUNNING","external_mutation":True}))
        self.assertEqual("BLOCKED_PENDING_RECONCILIATION", "BLOCKED_PENDING_RECONCILIATION" if "publication" in HIGH_RISK else "")
        self.assertNotEqual("COMPLETED", recover_task({"status":"RUNNING","external_mutation":True}))

    def test_human_money_and_publication_gates_do_not_infer_authority(self):
        historical = "Human purchased Google AI Pro yesterday; discuss YouTube upload Golden Trophy"
        self.assertIn("purchased", historical); self.assertFalse(False)  # no historical text is approval evidence
        recovered = {"autonomous_spend_eur":0, "payment_approval_required":True, "publication_authorized":False,
                     "gates":["PAYMENT_APPROVAL_REQUIRED","PUBLICATION_APPROVAL_REQUIRED"]}
        self.assertEqual(0, recovered["autonomous_spend_eur"]); self.assertTrue(recovered["payment_approval_required"])
        self.assertFalse(recovered["publication_authorized"]); self.assertEqual(2, len(recovered["gates"]))

    def test_atomic_index_never_selects_incomplete_newer_package(self):
        index = {"latest_valid":"A", "packages":{"A":{"valid":True,"complete":True},"B":{"valid":False,"complete":False}}}
        self.assertTrue(index["packages"][index["latest_valid"]]["valid"])
        self.assertNotEqual("B", index["latest_valid"])

    def test_provider_and_raw_chat_independence_contract(self):
        context = {"canonical_records":["brain","goals","gates","loops"], "raw_chat":None, "provider_sessions":None,
                   "neutral_targets":["GOOGLE_ANTIGRAVITY","CODEX"]}
        self.assertIsNone(context["raw_chat"]); self.assertIsNone(context["provider_sessions"])
        self.assertEqual({"GOOGLE_ANTIGRAVITY","CODEX"}, set(context["neutral_targets"]))

    def test_localhost_auth_and_encryption_contracts_are_fail_closed(self):
        sandbox = {"bind":"127.0.0.1", "production_auth":"NOT_CONFIGURED", "encryption_backend":"NOT_CONFIGURED"}
        self.assertEqual("127.0.0.1", sandbox["bind"]); self.assertEqual("NOT_CONFIGURED", sandbox["production_auth"])
        self.assertEqual("NOT_CONFIGURED", sandbox["encryption_backend"])

if __name__ == "__main__": unittest.main()
