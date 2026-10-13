import pytest

from courier_orchestrator.capsules import Capsule, CapsuleRegistry, CapsuleStatus, RegistryError, validate_capsule


def make(**kw):
    base = dict(capsule_id="pdf-invoice-extract", version="1.0.0", author="alice", license="MIT",
                task_class="extraction", problem_class="structured extraction from invoices",
                inputs={"document": "pdf"}, planning_pattern=["split", "extract", "merge"],
                worker_requirements={"model_tier": "small"}, verification_pattern=["schema_check", "sum_check"],
                failure_modes=["ocr_noise"], cost_profile={"max_usd": 0.05},
                output_schema={"type": "object", "required": ["total"]},
                code={"helpers.py": "import json\n\ndef total(xs):\n    return sum(xs)\n"})
    base.update(kw)
    return Capsule(**base)


@pytest.fixture
def reg(tmp_path):
    return CapsuleRegistry(tmp_path / "index.json")


def test_valid_capsule_passes():
    assert validate_capsule(make()).ok


def test_secret_rejected(reg):
    c = make(inputs={"document": "pdf", "hint": "AKIAABCDEFGHIJKLMNOP"})
    r = validate_capsule(c)
    assert not r.ok and any(e.startswith("secret:") for e in r.errors)
    assert reg.upload(c)["status"] == "rejected"


def test_private_key_in_code_rejected():
    c = make(code={"k.py": "K = '-----BEGIN RSA PRIVATE KEY-----'\n"})
    assert not validate_capsule(c).ok


def test_disallowed_license_rejected(reg):
    c = make(license="GPL-3.0-only")
    r = validate_capsule(c)
    assert not r.ok and any(e.startswith("license:") for e in r.errors)
    assert reg.upload(c)["status"] == "rejected"


@pytest.mark.parametrize("src", ["import subprocess\n", "from os import path\n", "eval('1')\n", "import socket.x\n"])
def test_forbidden_code_rejected(src):
    assert not validate_capsule(make(code={"x.py": src})).ok


def test_size_limit():
    assert not validate_capsule(make(failure_modes=["x" * 300_000])).ok


def test_missing_field_and_private_data():
    d = make().to_dict()
    del d["output_schema"]
    assert not validate_capsule(d).ok
    assert not validate_capsule(make(inputs={"path": "/home/dennis/kunde/secret.pdf"})).ok


def test_no_distribution_without_independent_review(reg):
    c = make()
    reg.upload(c)
    assert reg.status(c.key) is CapsuleStatus.QUARANTINED
    with pytest.raises(RegistryError):
        reg.approve(c.key, "dennis")
    with pytest.raises(RegistryError):
        reg.review(c.key, "alice", True)  # self-review
    with pytest.raises(RegistryError):
        reg.approve(c.key, "dennis")
    assert reg.distribution_manifest() == []


def test_author_cannot_human_approve(reg):
    c = make()
    reg.upload(c)
    reg.review(c.key, "bob", True)
    with pytest.raises(RegistryError):
        reg.approve(c.key, "alice")


def test_full_flow_and_recall(reg, tmp_path):
    c = make()
    reg.upload(c)
    reg.review(c.key, "bob", True)
    reg.approve(c.key, "dennis")
    assert reg.distribution_manifest() == [{"key": c.key, "sha256": c.sha256()}]
    assert reg.trust("alice", "extraction") == 1
    reg.recall(c.key, "wrong totals")
    assert reg.distribution_manifest() == []
    assert reg.recalled_keys() == [c.key]
    assert reg.trust("alice", "extraction") == -2
    reloaded = CapsuleRegistry(tmp_path / "index.json")
    assert reloaded.status(c.key) is CapsuleStatus.RECALLED


def test_tampered_capsule_not_distributed(reg):
    c = make()
    reg.upload(c)
    reg.review(c.key, "bob", True)
    reg.approve(c.key, "dennis")
    reg.index["capsules"][c.key]["capsule"]["cost_profile"] = {"max_usd": 99}
    assert reg.distribution_manifest() == []


def test_rejected_cannot_be_reviewed(reg):
    c = make(license="Proprietary")
    reg.upload(c)
    with pytest.raises(RegistryError):
        reg.review(c.key, "bob", True)
