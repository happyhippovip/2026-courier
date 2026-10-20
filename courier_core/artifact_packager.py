"""Automated Artifact Checkpoint Packager and Manifest Signer.

Bundles task outputs, test proofs, and evidence into tamper-evident,
cryptographically signed zip archives with traversal protection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from courier_core.receipt_signer import ReceiptSigner, SignedReceipt


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_safe_rel_path(rel_path: str) -> bool:
    """Check if relative path contains traversal attempts or absolute paths."""
    if not rel_path or not rel_path.strip():
        return False
    normalized = rel_path.replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized:
        return False
    parts = normalized.split("/")
    if any(p == ".." for p in parts):
        return False
    return True


@dataclass
class PackageSummary:
    """Summary of a packaged and signed checkpoint bundle."""

    package_path: str
    item_id: str
    file_count: int
    package_hash: str
    signature: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationReport:
    """Integrity and signature verification report for a checkpoint package."""

    is_valid: bool
    item_id: str | None = None
    verified_files_count: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ArtifactPackager:
    """Packs and verifies tamper-evident artifact bundles."""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.signer = ReceiptSigner(secret_key=self.secret_key)

    def pack(
        self,
        source_dir: str,
        output_path: str,
        item_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> PackageSummary:
        src_path = Path(source_dir)
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        files_map: dict[str, str] = {}
        file_paths: list[tuple[Path, str]] = []

        for p in sorted(src_path.rglob("*")):
            if p.is_file():
                rel = p.relative_to(src_path).as_posix()
                if not is_safe_rel_path(rel):
                    raise ValueError(f"Unsafe path detected: {rel}")
                h = _file_sha256(p)
                files_map[rel] = h
                file_paths.append((p, rel))

        manifest = {
            "item_id": item_id,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "files": files_map,
            "metadata": metadata or {},
        }

        # Cryptographically sign manifest
        signed_manifest = self.signer.sign(manifest)

        # Build zip
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p, rel in file_paths:
                zf.write(p, arcname=rel)
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))
            zf.writestr("signature.json", json.dumps(signed_manifest.to_dict(), indent=2))

        pkg_hash = _file_sha256(out_path)

        return PackageSummary(
            package_path=str(out_path),
            item_id=item_id,
            file_count=len(file_paths),
            package_hash=pkg_hash,
            signature=signed_manifest.signature,
        )

    def verify(
        self,
        package_path: str,
        secret_key: str | None = None,
    ) -> VerificationReport:
        pkg_path = Path(package_path)
        if not pkg_path.exists():
            return VerificationReport(is_valid=False, errors=[f"FILE_NOT_FOUND: {package_path}"])

        active_signer = ReceiptSigner(secret_key=secret_key) if secret_key else self.signer
        errors: list[str] = []

        try:
            with zipfile.ZipFile(pkg_path, "r") as zf:
                # 1. Path traversal check
                for member in zf.infolist():
                    if not is_safe_rel_path(member.filename):
                        errors.append(f"PATH_TRAVERSAL_DETECTED: {member.filename}")
                if errors:
                    return VerificationReport(is_valid=False, errors=errors)

                # 2. Check manifest and signature presence
                namelist = zf.namelist()
                if "manifest.json" not in namelist or "signature.json" not in namelist:
                    errors.append("MISSING_MANIFEST_OR_SIGNATURE")
                    return VerificationReport(is_valid=False, errors=errors)

                manifest_raw = zf.read("manifest.json").decode("utf-8")
                sig_raw = zf.read("signature.json").decode("utf-8")

                manifest_data = json.loads(manifest_raw)
                sig_data = json.loads(sig_raw)
                item_id = manifest_data.get("item_id")

                # 3. Verify signature
                sig_obj = SignedReceipt.from_dict(sig_data)
                # Ensure payload in signature envelope matches manifest
                if sig_obj.payload != manifest_data:
                    errors.append("SIGNATURE_MISMATCH: Manifest payload does not match signed envelope")

                v_res = active_signer.verify(sig_obj)
                if not v_res.is_valid:
                    errors.append(f"SIGNATURE_MISMATCH: {v_res.reason}")

                # 4. Verify file hashes
                files_map = manifest_data.get("files", {})
                verified_count = 0
                for rel, expected_hash in files_map.items():
                    if rel not in namelist:
                        errors.append(f"MISSING_FILE: {rel}")
                        continue
                    file_bytes = zf.read(rel)
                    actual_hash = _bytes_sha256(file_bytes)
                    if actual_hash != expected_hash:
                        errors.append(f"CONTENT_HASH_MISMATCH: {rel}")
                    else:
                        verified_count += 1

                return VerificationReport(
                    is_valid=len(errors) == 0,
                    item_id=item_id,
                    verified_files_count=verified_count,
                    errors=errors,
                )

        except Exception as exc:
            return VerificationReport(
                is_valid=False,
                errors=[f"ARCHIVE_READ_ERROR: {str(exc)}"],
            )


def pack_checkpoint(
    source_dir: str,
    output_path: str,
    item_id: str,
    secret_key: str,
    metadata: dict[str, Any] | None = None,
) -> PackageSummary:
    packager = ArtifactPackager(secret_key=secret_key)
    return packager.pack(source_dir, output_path, item_id, metadata=metadata)


def verify_checkpoint(
    package_path: str,
    secret_key: str,
) -> VerificationReport:
    packager = ArtifactPackager(secret_key=secret_key)
    return packager.verify(package_path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Artifact Checkpoint Packager & Verifier.")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # pack
    p_pack = subparsers.add_parser("pack")
    p_pack.add_argument("--source", required=True, help="Directory containing artifacts")
    p_pack.add_argument("--output", required=True, help="Destination zip path")
    p_pack.add_argument("--item", required=True, help="Work item ID")
    p_pack.add_argument("--key", required=True, help="Secret HMAC signing key")

    # verify
    p_ver = subparsers.add_parser("verify")
    p_ver.add_argument("--package", required=True, help="Zip package path")
    p_ver.add_argument("--key", required=True, help="Secret HMAC signing key")

    args = parser.parse_args(argv)

    if args.subcommand == "pack":
        packager = ArtifactPackager(secret_key=args.key)
        summary = packager.pack(
            source_dir=args.source,
            output_path=args.output,
            item_id=args.item,
        )
        print(json.dumps({"status": "PACKED", "summary": summary.to_dict()}))
        return 0

    elif args.subcommand == "verify":
        packager = ArtifactPackager(secret_key=args.key)
        report = packager.verify(package_path=args.package)
        print(json.dumps({"status": "VERIFIED", "report": report.to_dict()}))
        return 0 if report.is_valid else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
