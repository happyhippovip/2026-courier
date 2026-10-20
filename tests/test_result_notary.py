"""Tests for courier_core.result_notary - Cryptographic Result Notary & Transparency Merkle Tree."""

from __future__ import annotations

import json
import pytest

from courier_core.result_notary import (
    MerkleTree,
    MerkleProof,
    ResultNotary,
    NotaryBatchRecord,
    TamperedProofError,
    verify_inclusion_proof,
    main,
)


def test_merkle_tree_construction_and_inclusion_proof():
    leaves = [b"result-packet-1", b"result-packet-2", b"result-packet-3", b"result-packet-4"]
    tree = MerkleTree.from_leaves(leaves)

    assert len(tree.root) == 64

    # Generate proof for index 1 (result-packet-2)
    leaf_hash = tree.get_leaf_hash(1)
    proof = tree.generate_proof(1)

    # Verify proof
    assert verify_inclusion_proof(leaf_hash=leaf_hash, proof=proof, root=tree.root) is True


def test_merkle_tree_odd_number_of_leaves():
    leaves = [b"tx-1", b"tx-2", b"tx-3"]
    tree = MerkleTree.from_leaves(leaves)

    assert len(tree.root) == 64

    for idx in range(len(leaves)):
        leaf_hash = tree.get_leaf_hash(idx)
        proof = tree.generate_proof(idx)
        assert verify_inclusion_proof(leaf_hash=leaf_hash, proof=proof, root=tree.root) is True


def test_tampered_leaf_or_sibling_fails_verification():
    leaves = [b"alpha", b"beta", b"gamma", b"delta"]
    tree = MerkleTree.from_leaves(leaves)

    leaf_hash = tree.get_leaf_hash(0)
    proof = tree.generate_proof(0)

    # Valid check
    assert verify_inclusion_proof(leaf_hash=leaf_hash, proof=proof, root=tree.root) is True

    # Tampered leaf hash
    tampered_leaf = "0" * 64
    assert verify_inclusion_proof(leaf_hash=tampered_leaf, proof=proof, root=tree.root) is False

    # Tampered sibling in proof
    tampered_proof = [("right", "f" * 64)] + proof[1:]
    assert verify_inclusion_proof(leaf_hash=leaf_hash, proof=tampered_proof, root=tree.root) is False


def test_result_notary_batch_lifecycle(tmp_path):
    log_dir = tmp_path / "notary_log"
    notary = ResultNotary(log_dir=log_dir, secret_key="notary-attestation-secret")

    batch = [
        {"task_id": "T-101", "result": "PASS", "worker": "win-1"},
        {"task_id": "T-102", "result": "PASS", "worker": "win-2"},
        {"task_id": "T-103", "result": "PASS", "worker": "win-1"},
    ]

    record = notary.notarize_batch(batch_id="batch-001", items=batch)
    assert record.batch_id == "batch-001"
    assert record.item_count == 3
    assert record.signature != ""

    # Generate proof for T-102
    proof = notary.generate_item_proof(batch_id="batch-001", item_id="T-102")
    assert proof.item_id == "T-102"
    assert proof.batch_id == "batch-001"

    # Verify proof through notary
    assert notary.verify_item_proof(proof) is True

    # Verifying proof with wrong secret fails
    untrusted_notary = ResultNotary(log_dir=log_dir, secret_key="wrong-key")
    with pytest.raises(TamperedProofError, match="Notary signature verification failed"):
        untrusted_notary.verify_item_proof(proof)

    # Even without secret_key, a self-consistent proof with a different root_hash than the recorded batch must fail
    keyless_notary = ResultNotary(log_dir=log_dir, secret_key=None)
    fake_tree = MerkleTree.from_leaves([b"fake-leaf-1", b"fake-leaf-2"])
    forged_proof = MerkleProof(
        batch_id="batch-001",
        item_id="T-102",
        leaf_hash=fake_tree.get_leaf_hash(0),
        root_hash=fake_tree.root,
        proof_path=fake_tree.generate_proof(0),
        notary_signature="",
    )
    with pytest.raises(TamperedProofError, match="root_hash does not match"):
        keyless_notary.verify_item_proof(forged_proof)

    # Duplicate task_id in batch must raise NotaryError
    from courier_core.result_notary import NotaryError
    with pytest.raises(NotaryError, match="Duplicate task_id"):
        notary.notarize_batch(
            batch_id="batch-dup",
            items=[
                {"task_id": "T-DUP", "result": "PASS"},
                {"task_id": "T-DUP", "result": "PASS"},
            ],
        )


def test_cli_result_notary(tmp_path, monkeypatch, capsys):
    log_dir = tmp_path / "cli_notary"
    batch_file = tmp_path / "batch.json"

    items = [
        {"task_id": "CLI-1", "status": "DONE"},
        {"task_id": "CLI-2", "status": "DONE"},
    ]
    batch_file.write_text(json.dumps(items), encoding="utf-8")

    # Notarize
    monkeypatch.setattr(
        "sys.argv",
        [
            "result_notary.py",
            "notarize",
            "--dir",
            str(log_dir),
            "--batch-id",
            "cli-batch-1",
            "--file",
            str(batch_file),
            "--secret",
            "cli-secret-key",
        ],
    )
    main()
    capsys.readouterr()

    # Generate & Verify Proof
    proof_file = tmp_path / "proof.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "result_notary.py",
            "prove",
            "--dir",
            str(log_dir),
            "--batch-id",
            "cli-batch-1",
            "--item-id",
            "CLI-2",
            "--output",
            str(proof_file),
        ],
    )
    main()
    capsys.readouterr()
    assert proof_file.exists()

    # Verify Proof
    monkeypatch.setattr(
        "sys.argv",
        [
            "result_notary.py",
            "verify",
            "--dir",
            str(log_dir),
            "--proof",
            str(proof_file),
            "--secret",
            "cli-secret-key",
        ],
    )
    main()
    out = capsys.readouterr().out
    assert "PROOF_VERIFIED_OK" in out
