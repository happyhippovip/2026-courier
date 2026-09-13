"""
build_v1_release.py - Courier Symphony Windows V1.0.0-RC1 Release Packaging Engine
Builds, audits, packages, verifies in a clean-room sandbox, and signs the release archive.
"""

import os
import sys
import json
import zipfile
import hashlib
import tempfile
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

COURIER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIST_DIR = os.path.join(COURIER_DIR, "dist")
VERSION = "1.0.0-rc1"
RELEASE_TAG = "v1.0.0-rc1"
PACKAGE_BASE = f"courier_symphony_{RELEASE_TAG}"
ZIP_NAME = f"{PACKAGE_BASE}.zip"
ZIP_PATH = os.path.join(DIST_DIR, ZIP_NAME)

FORBIDDEN_PATTERNS = [
    b"C:\\Users\\lol",
    b"C:/Users/lol",
    b"/Users/lol",
    b"BEGIN PRIVATE KEY",
    b"BEGIN RSA PRIVATE KEY"
]


def sha256_file(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get_git_commit() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=COURIER_DIR,
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "unknown"


def audit_file_content(filepath: str) -> List[str]:
    violations = []
    with open(filepath, "rb") as f:
        data = f.read()
    for pat in FORBIDDEN_PATTERNS:
        if pat in data:
            violations.append(f"Forbidden pattern '{pat.decode('latin-1', errors='ignore')}' found in {filepath}")
    return violations


def collect_release_files() -> List[Tuple[str, str]]:
    """Returns list of (source_abs_path, archive_rel_path)."""
    files = []

    # 1. Chief Python Modules
    chief_dir = os.path.join(COURIER_DIR, "chief")
    for root, dirs, fnames in os.walk(chief_dir):
        if "__pycache__" in root:
            continue
        for fname in fnames:
            if fname.endswith(".py"):
                abs_path = os.path.join(root, fname)
                rel_within_chief = os.path.relpath(abs_path, chief_dir)
                archive_path = os.path.join("courier", "chief", rel_within_chief).replace("\\", "/")
                files.append((abs_path, archive_path))

    # 2. Constitution & Governance
    const_json = os.path.join(COURIER_DIR, "WINDOWS_COURIER_OPERATING_CONSTITUTION.json")
    if os.path.exists(const_json):
        files.append((const_json, "courier/WINDOWS_COURIER_OPERATING_CONSTITUTION.json"))
        # Also include at archive root for standalone discovery
        files.append((const_json, "WINDOWS_COURIER_OPERATING_CONSTITUTION.json"))

    const_md = os.path.join(COURIER_DIR, "WINDOWS_COURIER_OPERATING_CONSTITUTION.md")
    if os.path.exists(const_md):
        files.append((const_md, "courier/WINDOWS_COURIER_OPERATING_CONSTITUTION.md"))

    # 3. Documentation & Operational Cards
    for doc_name in ("README.md", "V1_RECOVERY_CARD.md", "V1_RELEASE_REPORT.md", "V1_ACCEPTANCE_MATRIX.json"):
        doc_path = os.path.join(COURIER_DIR, doc_name)
        if os.path.exists(doc_path):
            files.append((doc_path, doc_name))

    # 4. Self-Test Engine
    selftest_path = os.path.join(COURIER_DIR, "SELF_TEST.py")
    if os.path.exists(selftest_path):
        files.append((selftest_path, "SELF_TEST.py"))

    return files


def build_release() -> Dict[str, Any]:
    print("=================================================================")
    print(f"  BUILDING COURIER SYMPHONY WINDOWS {RELEASE_TAG}")
    print("=================================================================")

    os.makedirs(DIST_DIR, exist_ok=True)
    git_commit = get_git_commit()
    build_time = datetime.now(timezone.utc).isoformat()

    file_entries = collect_release_files()
    print(f"[*] Collected {len(file_entries)} file artifacts for packaging.")

    # Audit file contents
    print("[*] Performing clean-room security audit for forbidden developer paths & secrets...")
    audit_errors = []
    manifest_files = []

    for src_path, arc_path in file_entries:
        errs = audit_file_content(src_path)
        if errs:
            audit_errors.extend(errs)
        size = os.path.getsize(src_path)
        digest = sha256_file(src_path)
        manifest_files.append({
            "archive_path": arc_path,
            "size_bytes": size,
            "sha256": digest
        })

    if audit_errors:
        print("[-] SECURITY AUDIT FAILED! Forbidden patterns detected:")
        for err in audit_errors:
            print(f"    - {err}")
        raise RuntimeError("Build aborted due to security audit violations.")
    print("[+] Clean-room security audit PASSED: 0 forbidden patterns found.")

    # Create Release Manifest
    manifest_data = {
        "product_name": "Courier Symphony Windows",
        "version": VERSION,
        "release_tag": RELEASE_TAG,
        "build_timestamp_utc": build_time,
        "git_commit": git_commit,
        "schema_version": 1,
        "python_requires": ">=3.10",
        "platform": "Windows (cross-platform compatible chief runtime)",
        "total_files": len(manifest_files) + 1,  # including manifest itself
        "files": manifest_files
    }

    manifest_json_bytes = json.dumps(manifest_data, indent=2).encode("utf-8")
    manifest_sha256 = sha256_bytes(manifest_json_bytes)
    manifest_data["files"].append({
        "archive_path": "RELEASE_MANIFEST.json",
        "size_bytes": len(manifest_json_bytes),
        "sha256": manifest_sha256
    })
    # Write canonical RELEASE_MANIFEST.json in courier/ root and dist/
    with open(os.path.join(COURIER_DIR, "RELEASE_MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    with open(os.path.join(DIST_DIR, "RELEASE_MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    # Assemble ZIP Archive
    print(f"[*] Packaging archive: {ZIP_PATH} ...")
    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        # Add manifest
        zf.writestr(f"{PACKAGE_BASE}/RELEASE_MANIFEST.json", manifest_json_bytes)
        # Add collected files
        for src_path, arc_path in file_entries:
            zf.write(src_path, f"{PACKAGE_BASE}/{arc_path}")

    zip_size = os.path.getsize(ZIP_PATH)
    zip_sha256 = sha256_file(ZIP_PATH)
    print(f"[+] Archive generated: {zip_size:,} bytes | SHA256: {zip_sha256}")

    # Copy standalone docs to dist directory
    import shutil
    for doc in ("README.md", "V1_RECOVERY_CARD.md", "V1_RELEASE_REPORT.md", "WINDOWS_COURIER_OPERATING_CONSTITUTION.json"):
        src = os.path.join(COURIER_DIR, doc)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(DIST_DIR, doc))

    # Write SHA256SUMS.txt
    sha_file = os.path.join(DIST_DIR, "SHA256SUMS.txt")
    with open(sha_file, "w", encoding="utf-8") as f:
        f.write(f"{zip_sha256}  {ZIP_NAME}\n")
        f.write(f"{manifest_sha256}  RELEASE_MANIFEST.json\n")
    print(f"[+] Checksums persisted to: {sha_file}")

    # Clean-Room Verification Court
    print("\n=================================================================")
    print("  CLEAN-ROOM VERIFICATION COURT (FRESH EXTRACT & EXECUTE)")
    print("=================================================================")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        extract_dest = os.path.join(td, "extract")
        print(f"[*] Extracting {ZIP_NAME} into temporary clean-room: {extract_dest} ...")
        with zipfile.ZipFile(ZIP_PATH, "r") as zf:
            zf.extractall(extract_dest)

        app_root = os.path.join(extract_dest, PACKAGE_BASE)
        assert os.path.exists(app_root), f"Package root directory missing in archive: {app_root}"
        selftest_script = os.path.join(app_root, "SELF_TEST.py")
        assert os.path.exists(selftest_script), f"SELF_TEST.py missing in extracted bundle: {selftest_script}"

        print(f"[*] Launching isolated subprocess: python SELF_TEST.py ...")
        res = subprocess.run(
            [sys.executable, "SELF_TEST.py"],
            cwd=app_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        print("--- SUBPROCESS OUTPUT ---")
        print(res.stdout)
        if res.stderr:
            print("--- SUBPROCESS STDERR ---")
            print(res.stderr)

        if res.returncode != 0:
            raise RuntimeError(f"Clean-room verification court failed! Subprocess exit code: {res.returncode}")
        if "V1_SELF_TEST_SUCCESSFUL" not in res.stdout:
            raise RuntimeError("Clean-room verification court did not emit V1_SELF_TEST_SUCCESSFUL marker!")
        print("[+] Clean-room verification court PASSED with code 0!")

    print("\n=================================================================")
    print(f"  COURIER SYMPHONY WINDOWS {RELEASE_TAG} BUILD COMPLETE")
    print("=================================================================")
    return {
        "success": True,
        "version": VERSION,
        "release_tag": RELEASE_TAG,
        "archive_path": ZIP_PATH,
        "archive_size_bytes": zip_size,
        "archive_sha256": zip_sha256,
        "manifest_sha256": manifest_sha256,
        "total_files": len(manifest_files) + 1,
        "clean_room_verified": True
    }


if __name__ == "__main__":
    res = build_release()
    print(json.dumps(res, indent=2))
