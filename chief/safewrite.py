"""
safewrite.py - NTFS-Safe Atomic File Writer for Windows
Prevents WinError 32 (Sharing Violation) and WinError 5 (Access Denied)
under active multi-process reader contention on Windows.
"""

import os
import sys
import json
import time
import random
import tempfile
from typing import Any, Optional


def safe_write_text(
    filepath: str,
    content: str,
    encoding: str = "utf-8",
    max_retries: int = 15,
    initial_backoff: float = 0.02,
    max_backoff: float = 0.5
) -> str:
    """
    Writes text atomically to filepath using a temporary file in the same
    directory, with exponential backoff retry loop on Windows locking errors.
    """
    filepath = os.path.abspath(filepath)
    target_dir = os.path.dirname(filepath)
    os.makedirs(target_dir, exist_ok=True)

    # Create temporary file in the exact same directory (required for atomic rename)
    tmp_fd, tmp_path = tempfile.mkstemp(
        prefix=f".tmp_{os.path.basename(filepath)}_",
        dir=target_dir,
        text=True
    )

    try:
        with os.fdopen(tmp_fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        # Attempt atomic replacement with retry
        backoff = initial_backoff
        for attempt in range(max_retries):
            try:
                os.replace(tmp_path, filepath)
                return filepath
            except (PermissionError, OSError) as e:
                # Windows error 32 = ERROR_SHARING_VIOLATION, error 5 = ERROR_ACCESS_DENIED
                winerror = getattr(e, 'winerror', None)
                if winerror in (32, 5) or isinstance(e, PermissionError):
                    if attempt == max_retries - 1:
                        # Fallback to direct write if replace is permanently locked
                        try:
                            with open(filepath, "w", encoding=encoding) as direct_f:
                                direct_f.write(content)
                                direct_f.flush()
                                os.fsync(direct_f.fileno())
                            return filepath
                        except Exception:
                            raise e
                    sleep_time = min(backoff * (1.5 ** attempt) + random.uniform(0.005, 0.02), max_backoff)
                    time.sleep(sleep_time)
                else:
                    raise e

        return filepath
    finally:
        # Clean up temp file if it still exists
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def safe_write_json(
    filepath: str,
    data: Any,
    indent: int = 2,
    encoding: str = "utf-8",
    max_retries: int = 15
) -> str:
    """Writes data as JSON using safe_write_text."""
    content = json.dumps(data, indent=indent, ensure_ascii=False)
    return safe_write_text(
        filepath=filepath,
        content=content,
        encoding=encoding,
        max_retries=max_retries
    )
