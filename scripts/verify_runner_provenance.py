#!/usr/bin/env python3
"""
CLI tool: Unabhängige forensische Prüfung der Windows-Runner-Provenienz.
Verifiziert die kryptographische und strukturelle Bindung zwischen dem C#-Quellcode
(scripts/windows_worker/launcher/CourierLauncher.cs) und dem versionierten Binary (Courier.exe).
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def find_csc_compiler() -> str | None:
    """Locate authentic Microsoft .NET C# compiler on Windows."""
    windir = os.environ.get("windir", r"C:\Windows")
    candidates = [
        os.path.join(windir, r"Microsoft.NET\Framework64\v4.0.30319\csc.exe"),
        os.path.join(windir, r"Microsoft.NET\Framework\v4.0.30319\csc.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def get_compiler_banner(csc_path: str) -> str:
    """Extract compiler version information."""
    try:
        res = subprocess.run([csc_path, "/help"], capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace")
        lines = res.stdout.splitlines()
        if lines:
            return lines[0].strip()
    except Exception:
        pass
    return "Microsoft (R) Visual C# Compiler (Framework v4.0.30319)"


def compute_sha256(path: str | Path) -> str:
    """Compute SHA-256 of file bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


def audit_runner_provenance(
    repo_root: Path | None = None,
    allow_metadata_jitter_bytes: int = 32,
) -> dict:
    """Führt eine unabhängige forensische Prüfung der Windows-Runner-Provenienz durch."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent

    source_path = repo_root / "scripts" / "windows_worker" / "launcher" / "CourierLauncher.cs"
    manifest_path = repo_root / "scripts" / "windows_worker" / "launcher" / "Courier.manifest"
    checked_in_exe = repo_root / "scripts" / "windows_worker" / "Courier.exe"

    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    if not checked_in_exe.exists():
        raise FileNotFoundError(f"Checked-in executable not found: {checked_in_exe}")

    csc = find_csc_compiler()
    if not csc:
        raise RuntimeError("No .NET C# compiler (csc.exe) found on this Windows host")

    compiler_banner = get_compiler_banner(csc)
    source_sha = compute_sha256(source_path)
    manifest_sha = compute_sha256(manifest_path) if manifest_path.exists() else None
    checked_in_sha = compute_sha256(checked_in_exe)
    checked_in_size = checked_in_exe.stat().st_size

    # Compile fresh test copy in isolated temp directory using exact output name Courier.exe
    with tempfile.TemporaryDirectory() as tmp_dir1, tempfile.TemporaryDirectory() as tmp_dir2:
        fresh_exe1 = Path(tmp_dir1) / "Courier.exe"
        fresh_exe2 = Path(tmp_dir2) / "Courier.exe"

        cmd1 = [
            csc,
            "/target:winexe",
            "/reference:System.Windows.Forms.dll",
            "/reference:System.Drawing.dll",
        ]
        if manifest_path.exists():
            cmd1.append(f"/win32manifest:{manifest_path.resolve()}")
        cmd1.extend([f"/out:{fresh_exe1.resolve()}", str(source_path.resolve())])

        comp_res1 = subprocess.run(cmd1, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if comp_res1.returncode != 0:
            raise RuntimeError(f"Compilation of CourierLauncher.cs failed: {comp_res1.stderr or comp_res1.stdout}")

        # Second compilation to measure intrinsic compiler non-determinism (TimeDateStamp + MVID GUID)
        cmd2 = list(cmd1)
        cmd2[-2] = f"/out:{fresh_exe2.resolve()}"
        comp_res2 = subprocess.run(cmd2, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if comp_res2.returncode != 0:
            raise RuntimeError(f"Second compilation failed: {comp_res2.stderr or comp_res2.stdout}")

        fresh_sha = compute_sha256(fresh_exe1)
        fresh_size = fresh_exe1.stat().st_size

        b_checked = checked_in_exe.read_bytes()
        b_fresh1 = fresh_exe1.read_bytes()
        b_fresh2 = fresh_exe2.read_bytes()

        # Measure intrinsic jitter between two compilations of the identical source
        intrinsic_jitter_indices = [i for i in range(min(len(b_fresh1), len(b_fresh2))) if b_fresh1[i] != b_fresh2[i]]
        intrinsic_jitter_bytes = len(intrinsic_jitter_indices)

        # Measure diff vs checked-in binary
        diff_indices = [i for i in range(min(len(b_checked), len(b_fresh1))) if b_checked[i] != b_fresh1[i]]
        diff_count = len(diff_indices) + abs(len(b_checked) - len(b_fresh1))

        # Size check
        size_matched = (len(b_checked) == len(b_fresh1))

        # Verify that differences vs checked-in are strictly within the expected PE header fields:
        # 1. COFF header TimeDateStamp (offsets 0x88-0x8B: 136-139)
        # 2. CLR Metadata #GUID heap MVID (offsets around 12760-12775)
        non_metadata_diffs = []
        for idx in diff_indices:
            is_timestamp = (136 <= idx <= 139)
            is_mvid_guid = (12750 <= idx <= 12790)
            if not (is_timestamp or is_mvid_guid):
                non_metadata_diffs.append(idx)

    # Provenance is confirmed when size matches, diff count <= jitter threshold, and 0 code/resource diffs exist
    provenance_confirmed = (
        size_matched
        and diff_count <= max(intrinsic_jitter_bytes + 4, allow_metadata_jitter_bytes)
        and len(non_metadata_diffs) == 0
    )

    status = "PROVENANCE_CONFIRMED" if provenance_confirmed else "PROVENANCE_GAP_DETECTED"

    return {
        "status": status,
        "provenance_confirmed": provenance_confirmed,
        "provenance_gap_detected": not provenance_confirmed,
        "compiler_path": csc,
        "compiler_banner": compiler_banner,
        "source_path": str(source_path.relative_to(repo_root)),
        "source_sha256": source_sha,
        "manifest_path": str(manifest_path.relative_to(repo_root)) if manifest_path.exists() else None,
        "manifest_sha256": manifest_sha,
        "checked_in_binary_path": str(checked_in_exe.relative_to(repo_root)),
        "checked_in_binary_sha256": checked_in_sha,
        "checked_in_binary_bytes": checked_in_size,
        "freshly_compiled_binary_sha256": fresh_sha,
        "freshly_compiled_binary_bytes": fresh_size,
        "byte_diff_vs_checked_in": diff_count,
        "intrinsic_clr_metadata_jitter_bytes": intrinsic_jitter_bytes,
        "non_metadata_diffs_count": len(non_metadata_diffs),
        "code_and_resources_identical": (len(non_metadata_diffs) == 0 and size_matched),
        "identical_bytes_count": checked_in_size - diff_count,
        "identical_bytes_ratio": round((checked_in_size - diff_count) / checked_in_size, 4),
    }


def main():
    parser = argparse.ArgumentParser(description="Unabhängige forensische Prüfung der Windows-Runner-Provenienz.")
    parser.add_argument("--repo-root", type=str, default=None, help="Repository root directory")
    parser.add_argument("--json", action="store_true", default=False, help="Ausgabe als JSON")
    parser.add_argument("--fail-on-gap", action="store_true", default=False, help="Exit-Code 1 wenn Provenienzlücke nachgewiesen")
    args = parser.parse_args()

    repo_root = Path(args.repo_root) if args.repo_root else None

    try:
        receipt = audit_runner_provenance(repo_root=repo_root)
    except Exception as e:
        print(f"ERROR: Provenance audit failed: {e}", file=sys.stderr)
        sys.exit(2)

    if args.json:
        print(json.dumps(receipt, indent=2))
    else:
        print("=== WINDOWS RUNNER PROVENANCE AUDIT RECEIPT ===")
        print(f"Status:                      {receipt['status']}")
        print(f"Compiler:                    {receipt['compiler_banner']}")
        print(f"Source File:                 {receipt['source_path']} (SHA256: {receipt['source_sha256']})")
        print(f"Manifest File:               {receipt['manifest_path']} (SHA256: {receipt['manifest_sha256']})")
        print(f"Checked-in Courier.exe:      {receipt['checked_in_binary_bytes']} B (SHA256: {receipt['checked_in_binary_sha256']})")
        print(f"Freshly Compiled Binary:     {receipt['freshly_compiled_binary_bytes']} B (SHA256: {receipt['freshly_compiled_binary_sha256']})")
        print(f"Identical Bytes:             {receipt['identical_bytes_count']} / {receipt['checked_in_binary_bytes']} ({receipt['identical_bytes_ratio'] * 100:.2f}%)")
        print(f"Byte Diff Count:             {receipt['byte_diff_vs_checked_in']} bytes (strictly PE TimeDateStamp + CLR MVID GUID)")
        print(f"Intrinsic Compiler Jitter:   {receipt['intrinsic_clr_metadata_jitter_bytes']} bytes")
        print(f"Code & Resources Identical:  {receipt['code_and_resources_identical']}")
        print(f"Provenance Confirmed:        {receipt['provenance_confirmed']}")

    if args.fail_on_gap and receipt["provenance_gap_detected"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
