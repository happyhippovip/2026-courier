"""Cryptographic Result Notary & Transparency Merkle Tree.

Provides deterministic binary Merkle tree generation, inclusion proof creation,
proof verification, and tamper-evident notary transparency logging.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
from typing import Any, Optional


class NotaryError(Exception):
    """Base exception for notary operations."""


class TamperedProofError(NotaryError):
    """Raised when an inclusion proof or notary signature fails validation."""


class BatchNotFoundError(NotaryError):
    """Raised when a requested batch record is not found."""


class ItemNotFoundError(NotaryError):
    """Raised when a requested item is not found in a batch."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_pair(left: str, right: str) -> str:
    return _sha256((left + right).encode("utf-8"))


def _canonical_json_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return _sha256(raw.encode("utf-8"))


class MerkleTree:
    """Binary Merkle tree computing cryptographic root and inclusion proofs."""

    def __init__(self, leaves: list[str]) -> None:
        self.leaves = leaves
        self.levels: list[list[str]] = []
        self._build_tree()

    @classmethod
    def from_leaves(cls, raw_leaves: list[bytes | str]) -> MerkleTree:
        leaf_hashes = []
        for item in raw_leaves:
            if isinstance(item, bytes):
                leaf_hashes.append(_sha256(item))
            elif isinstance(item, str):
                leaf_hashes.append(_sha256(item.encode("utf-8")))
            else:
                leaf_hashes.append(_canonical_json_hash(item))
        return cls(leaf_hashes)

    def _build_tree(self) -> None:
        if not self.leaves:
            empty_root = _sha256(b"")
            self.levels = [[empty_root]]
            return

        current = list(self.leaves)
        self.levels.append(current)

        while len(current) > 1:
            next_level = []
            for i in range(0, len(current), 2):
                left = current[i]
                right = current[i + 1] if i + 1 < len(current) else left
                next_level.append(_hash_pair(left, right))
            self.levels.append(next_level)
            current = next_level

    @property
    def root(self) -> str:
        return self.levels[-1][0] if self.levels else _sha256(b"")

    def get_leaf_hash(self, index: int) -> str:
        return self.leaves[index]

    def generate_proof(self, index: int) -> list[tuple[str, str]]:
        """Generate inclusion proof as list of (direction, sibling_hash)."""
        if index < 0 or index >= len(self.leaves):
            raise IndexError("Leaf index out of bounds")

        proof = []
        curr_idx = index

        for lvl_idx in range(len(self.levels) - 1):
            level = self.levels[lvl_idx]
            is_right = (curr_idx % 2 == 1)

            if is_right:
                sibling_idx = curr_idx - 1
                direction = "left"
            else:
                sibling_idx = curr_idx + 1
                direction = "right"

            sibling_hash = level[sibling_idx] if sibling_idx < len(level) else level[curr_idx]
            proof.append((direction, sibling_hash))
            curr_idx //= 2

        return proof


def verify_inclusion_proof(leaf_hash: str, proof: list[tuple[str, str]], root: str) -> bool:
    """Verify that leaf_hash belongs to the tree represented by root."""
    curr = leaf_hash
    for direction, sibling in proof:
        if direction == "left":
            curr = _hash_pair(sibling, curr)
        elif direction == "right":
            curr = _hash_pair(curr, sibling)
        else:
            return False
    return hmac.compare_digest(curr, root)


@dataclass(frozen=True)
class NotaryBatchRecord:
    """Attested notarization record for an ordered batch of results."""

    batch_id: str
    root_hash: str
    item_count: int
    leaf_hashes: list[str]
    item_keys: list[str]
    timestamp: str
    signature: str

    def canonical_bytes(self) -> bytes:
        payload = {
            "batch_id": self.batch_id,
            "root_hash": self.root_hash,
            "item_count": self.item_count,
            "leaf_hashes": self.leaf_hashes,
            "item_keys": self.item_keys,
            "timestamp": self.timestamp,
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return canonical_json.encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NotaryBatchRecord:
        return cls(
            batch_id=str(data["batch_id"]),
            root_hash=str(data["root_hash"]),
            item_count=int(data["item_count"]),
            leaf_hashes=list(data.get("leaf_hashes", [])),
            item_keys=list(data.get("item_keys", [])),
            timestamp=str(data["timestamp"]),
            signature=str(data.get("signature", "")),
        )


@dataclass(frozen=True)
class MerkleProof:
    """Inclusion proof bundle for an individual item in a notarized batch."""

    batch_id: str
    item_id: str
    leaf_hash: str
    root_hash: str
    proof_path: list[tuple[str, str]]
    notary_signature: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MerkleProof:
        return cls(
            batch_id=str(data["batch_id"]),
            item_id=str(data["item_id"]),
            leaf_hash=str(data["leaf_hash"]),
            root_hash=str(data["root_hash"]),
            proof_path=[(p[0], p[1]) for p in data.get("proof_path", [])],
            notary_signature=str(data.get("notary_signature", "")),
        )


class ResultNotary:
    """Manages batch notarization and transparency inclusion proofs."""

    def __init__(self, log_dir: str | Path, secret_key: Optional[str] = None) -> None:
        self.log_dir = Path(log_dir)
        self.secret_key = secret_key
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _get_batch_path(self, batch_id: str) -> Path:
        return self.log_dir / f"{batch_id}.json"

    def notarize_batch(self, batch_id: str, items: list[dict[str, Any]]) -> NotaryBatchRecord:
        """Create Merkle tree for batch and persist signed notary record."""
        item_keys = []
        seen_keys: set[str] = set()
        leaf_hashes = []

        for idx, item in enumerate(items):
            key = str(item.get("task_id", item.get("id", f"item-{idx}")))
            if key in seen_keys:
                raise NotaryError(f"Duplicate task_id/item_id in batch {batch_id}: {key}")
            seen_keys.add(key)
            item_keys.append(key)
            leaf_hashes.append(_canonical_json_hash(item))

        tree = MerkleTree(leaf_hashes)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        temp_record = NotaryBatchRecord(
            batch_id=batch_id,
            root_hash=tree.root,
            item_count=len(items),
            leaf_hashes=leaf_hashes,
            item_keys=item_keys,
            timestamp=now_iso,
            signature="",
        )

        signature = ""
        if self.secret_key:
            signature = hmac.new(
                self.secret_key.encode("utf-8"),
                temp_record.canonical_bytes(),
                hashlib.sha256,
            ).hexdigest()

        record = NotaryBatchRecord(
            batch_id=batch_id,
            root_hash=tree.root,
            item_count=len(items),
            leaf_hashes=leaf_hashes,
            item_keys=item_keys,
            timestamp=now_iso,
            signature=signature,
        )

        batch_file = self._get_batch_path(batch_id)
        with open(batch_file, "w", encoding="utf-8") as f:
            json.dump(record.to_dict(), f, indent=2)

        return record

    def get_batch(self, batch_id: str) -> NotaryBatchRecord:
        batch_file = self._get_batch_path(batch_id)
        if not batch_file.exists():
            raise BatchNotFoundError(f"Batch {batch_id} not found")
        with open(batch_file, "r", encoding="utf-8") as f:
            return NotaryBatchRecord.from_dict(json.load(f))

    def generate_item_proof(self, batch_id: str, item_id: str) -> MerkleProof:
        """Generate Merkle inclusion proof for a specific item in a batch."""
        record = self.get_batch(batch_id)

        try:
            index = record.item_keys.index(item_id)
        except ValueError:
            raise ItemNotFoundError(f"Item {item_id} not found in batch {batch_id}")

        tree = MerkleTree(record.leaf_hashes)
        proof_path = tree.generate_proof(index)

        return MerkleProof(
            batch_id=batch_id,
            item_id=item_id,
            leaf_hash=record.leaf_hashes[index],
            root_hash=record.root_hash,
            proof_path=proof_path,
            notary_signature=record.signature,
        )

    def verify_item_proof(self, proof: MerkleProof) -> bool:
        """Verify Merkle inclusion proof, batch root binding, and optional notary signature."""
        # 1. Verify Merkle Path
        if not verify_inclusion_proof(proof.leaf_hash, proof.proof_path, proof.root_hash):
            return False

        # 2. Verify against stored batch root hash
        record = self.get_batch(proof.batch_id)
        if proof.root_hash != record.root_hash:
            raise TamperedProofError("Proof root_hash does not match recorded batch root_hash")

        # 3. Verify Notary Signature if secret key is configured
        if self.secret_key:
            expected_sig = hmac.new(
                self.secret_key.encode("utf-8"),
                record.canonical_bytes(),
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(proof.notary_signature, expected_sig):
                raise TamperedProofError("Notary signature verification failed")

        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Cryptographic Result Notary & Transparency Tree")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # notarize
    not_p = subparsers.add_parser("notarize", help="Notarize a batch of result records")
    not_p.add_argument("--dir", required=True, help="Notary log directory")
    not_p.add_argument("--batch-id", required=True, help="Batch ID")
    not_p.add_argument("--file", required=True, help="Path to JSON file containing items list")
    not_p.add_argument("--secret", help="Optional signing secret")

    # prove
    pro_p = subparsers.add_parser("prove", help="Generate inclusion proof for item")
    pro_p.add_argument("--dir", required=True, help="Notary log directory")
    pro_p.add_argument("--batch-id", required=True, help="Batch ID")
    pro_p.add_argument("--item-id", required=True, help="Item ID")
    pro_p.add_argument("--output", required=True, help="Output proof JSON file")

    # verify
    ver_p = subparsers.add_parser("verify", help="Verify Merkle inclusion proof")
    ver_p.add_argument("--dir", required=True, help="Notary log directory")
    ver_p.add_argument("--proof", required=True, help="Path to proof JSON file")
    ver_p.add_argument("--secret", help="Optional signing secret")

    args = parser.parse_args()
    notary = ResultNotary(log_dir=args.dir, secret_key=getattr(args, "secret", None))

    if args.action == "notarize":
        with open(args.file, "r", encoding="utf-8") as f:
            items = json.load(f)
        record = notary.notarize_batch(batch_id=args.batch_id, items=items)
        print(f"Notarized batch {record.batch_id} (root={record.root_hash[:16]}..., items={record.item_count})")

    elif args.action == "prove":
        proof = notary.generate_item_proof(batch_id=args.batch_id, item_id=args.item_id)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(proof.to_dict(), f, indent=2)
        print(f"Proof written to {args.output}")

    elif args.action == "verify":
        with open(args.proof, "r", encoding="utf-8") as f:
            proof = MerkleProof.from_dict(json.load(f))
        try:
            valid = notary.verify_item_proof(proof)
            if valid:
                print("PROOF_VERIFIED_OK")
            else:
                print("PROOF_VERIFICATION_FAILED")
                sys.exit(1)
        except NotaryError as e:
            print(f"PROOF_VERIFICATION_ERROR: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
