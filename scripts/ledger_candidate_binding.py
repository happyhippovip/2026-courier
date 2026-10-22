"""Gate 1: read-only ledger candidate binding.

Binds a ledger fingerprint (courier_core.projection.projection_hash) and the
journal hash-chain check (Journal.verify_chain) to the exact source candidate
(git HEAD SHA + tree). Never declares PASS or LEDGER_FROZEN: that requires an
independent acceptance. Opens the journal read-only and writes nothing except
the optional --out file.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from courier_core.journal import Journal  # noqa: E402
from courier_core.projection import PROJECTION_VERSION, last_seq, projection_hash  # noqa: E402

SCHEMA = "courier.ledger_candidate_binding/v1"


def _git(repo: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                             text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def build_binding(db_path: str | Path, repo: str | Path = ROOT) -> dict:
    repo = Path(repo)
    unknowns: list[str] = []
    source_sha = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    porcelain = _git(repo, "status", "--porcelain")
    if source_sha is None or tree is None:
        unknowns.append("source_identity_unavailable")
    dirty = None if porcelain is None else bool(porcelain)
    if dirty is None:
        unknowns.append("worktree_state_unknown")

    with Journal(db_path, readonly=True) as journal:
        chain = journal.verify_chain()
        fingerprint = projection_hash(journal.conn)
        seq = last_seq(journal.conn)

    bindable = chain.ok and dirty is False and not unknowns
    return {
        "schema": SCHEMA,
        "source_sha": source_sha,
        "tree": tree,
        "dirty": dirty,
        "projection_version": PROJECTION_VERSION,
        "ledger_fingerprint": fingerprint,
        "last_seq": seq,
        "journal_chain_ok": chain.ok,
        "journal_head_seq": chain.head_seq,
        "journal_head_hash": chain.head_hash,
        "journal_first_bad_seq": chain.first_bad_seq,
        "journal_defect": chain.reason,
        # Never PASS: PASS / LEDGER_FROZEN only via independent acceptance.
        "status": "CANDIDATE" if bindable else "NOT_BINDABLE",
        "unknowns": unknowns,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="path to the courier journal sqlite db")
    parser.add_argument("--repo", default=str(ROOT), help="git checkout of the candidate")
    parser.add_argument("--out", help="write binding JSON here (default: stdout)")
    args = parser.parse_args(argv)
    binding = build_binding(args.db, args.repo)
    text = json.dumps(binding, indent=2, sort_keys=True) + "\n"
    if args.out:
        dest = Path(args.out)
        if dest.is_symlink() or dest.parent.is_symlink():
            print(f"{dest}: refusing to follow a symlink", file=sys.stderr)
            return 2
        dest.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0 if binding["status"] == "CANDIDATE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
