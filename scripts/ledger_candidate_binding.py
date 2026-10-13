"""Gate 1: read-only ledger candidate binding.

Binds a ledger fingerprint (courier_core.projection.projection_hash) and the
journal hash-chain check (Journal.verify_chain) to the git candidate and to
the runtime that is actually loaded. Disk SHA and loaded runtime stay
separate fields. Append-only guards must be present: a journal that can still
be rewritten is not a candidate. Never declares PASS or LEDGER_FROZEN.
A blank identity or an unknown runtime blocks. Opens the journal read-only
and writes nothing except the optional --out file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from courier_core.build import build_identity  # noqa: E402
from courier_core.journal import Journal  # noqa: E402
from courier_core.projection import PROJECTION_VERSION, last_seq, projection_hash  # noqa: E402

SCHEMA = "courier.ledger_candidate_binding/v1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")


def _git(repo: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                             text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def _loaded_runtime() -> dict:
    ident = build_identity()
    return {
        "version": ident.get("version"),
        "build_id": ident.get("build_id"),
        "source_sha256": ident.get("source_sha256"),
        "python": ident.get("python"),
    }


def seal_of(body: dict) -> str:
    """Hash of the binding with the seal field removed. Key order does not matter."""
    payload = {k: v for k, v in body.items() if k != "seal"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def binding_intact(binding: dict) -> bool:
    """False when a field was changed after the seal was written."""
    if not isinstance(binding, dict):
        return False
    seal = binding.get("seal")
    if not isinstance(seal, str) or not _SHA64.fullmatch(seal):
        return False
    return seal == seal_of(binding)


def accepted(binding: dict) -> bool:
    """A candidate may be handed on only when it is sealed, complete, and not unknown.

    CANDIDATE is not PASS. UNKNOWN, a broken seal, a missing runtime, or any
    recorded unknown blocks.
    """
    if not binding_intact(binding) or binding.get("status") != "CANDIDATE":
        return False
    if binding.get("unknowns") or binding.get("guards_present") is not True:
        return False
    if binding.get("dirty") is not False or binding.get("journal_chain_ok") is not True:
        return False
    runtime = binding.get("runtime")
    if not isinstance(runtime, dict):
        return False
    return bool(runtime.get("version")) and bool(_SHA64.fullmatch(runtime.get("source_sha256") or ""))


def build_binding(db_path: str | Path, repo: str | Path = ROOT) -> dict:
    repo = Path(repo)
    unknowns: list[str] = []
    source_sha = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    porcelain = _git(repo, "status", "--porcelain")
    if not (isinstance(source_sha, str) and _SHA40.fullmatch(source_sha)
            and isinstance(tree, str) and _SHA40.fullmatch(tree)):
        unknowns.append("source_identity_unavailable")
    dirty = None if porcelain is None else bool(porcelain)
    if dirty is None:
        unknowns.append("worktree_state_unknown")
    runtime = _loaded_runtime()
    if not (isinstance(runtime.get("version"), str) and runtime["version"]
            and isinstance(runtime.get("source_sha256"), str)
            and _SHA64.fullmatch(runtime["source_sha256"])):
        unknowns.append("loaded_runtime_unknown")

    with Journal(db_path, readonly=True) as journal:
        chain = journal.verify_chain()
        fingerprint = projection_hash(journal.conn)
        seq = last_seq(journal.conn)
        guards = journal.guards_present()
    if not guards:
        unknowns.append("append_only_guards_missing")

    bindable = chain.ok and dirty is False and guards and not unknowns
    body = {
        "schema": SCHEMA,
        "source_sha": source_sha,
        "tree": tree,
        "dirty": dirty,
        "runtime": runtime,
        "guards_present": guards,
        "projection_version": PROJECTION_VERSION,
        "ledger_fingerprint": fingerprint,
        "last_seq": seq,
        "journal_chain_ok": chain.ok,
        "journal_head_seq": chain.head_seq,
        "journal_head_hash": chain.head_hash,
        "journal_first_bad_seq": chain.first_bad_seq,
        "journal_defect": chain.reason,
        # Never PASS: PASS / LEDGER_FROZEN only via independent acceptance.
        # Any unknown, including a relabelled UNKNOWN, stays NOT_BINDABLE.
        "status": "CANDIDATE" if bindable else "NOT_BINDABLE",
        "unknowns": unknowns,
    }
    body["seal"] = seal_of(body)
    return body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="path to the courier journal sqlite db")
    parser.add_argument("--repo", default=str(ROOT), help="git checkout of the candidate")
    parser.add_argument("--out", help="write binding JSON here (default: stdout)")
    args = parser.parse_args(argv)
    binding = build_binding(args.db, args.repo)
    text = json.dumps(binding, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0 if accepted(binding) else 1


if __name__ == "__main__":
    raise SystemExit(main())
