import hashlib
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class EvidenceIntegrityRecord:
    evidence_id: str
    file_path: str
    expected_hash: str
    expected_size: int
    creation_time: int
    producer: str
    source_sha: str

class EvidenceIntegrityException(Exception):
    pass

class EvidenceIntegrityVerifier:
    
    @staticmethod
    def calculate_hash(file_path: str) -> str:
        """Calculates SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    @staticmethod
    def create_record(evidence_id: str, file_path: str, creation_time: int, producer: str, source_sha: str) -> EvidenceIntegrityRecord:
        """Creates an integrity record from an existing file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Cannot create integrity record: file {file_path} not found.")
            
        return EvidenceIntegrityRecord(
            evidence_id=evidence_id,
            file_path=file_path,
            expected_hash=EvidenceIntegrityVerifier.calculate_hash(file_path),
            expected_size=os.path.getsize(file_path),
            creation_time=creation_time,
            producer=producer,
            source_sha=source_sha
        )
        
    @staticmethod
    def verify(record: EvidenceIntegrityRecord) -> bool:
        """
        Verifies that the file on disk still matches the recorded integrity metadata.
        Raises EvidenceIntegrityException if tampering or corruption is detected.
        Returns True if verified.
        """
        if not os.path.exists(record.file_path):
            raise EvidenceIntegrityException(f"Evidence file missing: {record.file_path}")
            
        actual_size = os.path.getsize(record.file_path)
        if actual_size != record.expected_size:
            raise EvidenceIntegrityException(f"Size mismatch: expected {record.expected_size}, got {actual_size}")
            
        actual_hash = EvidenceIntegrityVerifier.calculate_hash(record.file_path)
        if actual_hash != record.expected_hash:
            raise EvidenceIntegrityException(f"Hash mismatch: expected {record.expected_hash}, got {actual_hash}")
            
        return True
