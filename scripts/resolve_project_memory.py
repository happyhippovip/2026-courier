#!/usr/bin/env python3
"""Deterministic Read-Only Memory Resolver for Memory-Aware Courier v1.

Reads canonical project context from 2026-project-memory, selects relevant files,
extracts status-labelled facts, redacts any sensitive credentials, and produces
a verified Memory Context Package for Worker Job dispatch.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
from pathlib import Path

DEFAULT_MEMORY_REPO_PATH = Path("/Users/user/Downloads/2026-project-memory")
DEFAULT_MEMORY_REPO_NAME = "happyhippovip/2026-project-memory"

ALWAYS_CONSULTED_FILES = [
    "PROJECT_STATE.md",
    "AGENTS.md",
]

ALLOWED_MEMORY_FILES = {
    "PROJECT_STATE.md",
    "AGENTS.md",
    "PRODUCT_VISION.md",
    "DECISIONS.md",
    "IDEA_ARCHIVE.md",
    "BACKLOG.md",
    "TECHNICAL_CONTEXT.md",
    "OPEN_QUESTIONS.md",
    "LESSONS_LEARNED.md",
    "SOURCE_INDEX.md",
    "MEMORY_CHANGELOG.md",
}

STATUS_LABEL_PATTERN = re.compile(
    r"\b(VERIFIED_CURRENT|EXTERNAL_STATUS|HISTORICAL_DECISION|PLANNED|IDEA|CONFLICT|UNKNOWN|STATUS_BOUNDARY|PAUSED|PAUSED_EXTERNAL_GATE|DEFERRED|NOT VERIFIED|IN PROGRESS)\b"
)

SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(password|secret|token|api[_-]?key|bearer|oauth)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{8,})['\"]?"),
    re.compile(r"(ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z-_]{35})"),
]


def fail(message: str) -> None:
    raise SystemExit(f"MEMORY_RESOLVER_ERROR: {message}")


def get_memory_commit(repo_path: Path) -> str:
    """Reads git commit hash directly from .git directory without requiring external git CLI execution."""
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return "0000000000000000000000000000000000000000"

    head_file = git_dir / "HEAD"
    if not head_file.exists():
        return "0000000000000000000000000000000000000000"

    head_content = head_file.read_text(encoding="utf-8").strip()
    if head_content.startswith("ref:"):
        ref_path = head_content[4:].strip()
        ref_file = git_dir / ref_path
        if ref_file.exists():
            return ref_file.read_text(encoding="utf-8").strip()
        packed_refs_file = git_dir / "packed-refs"
        if packed_refs_file.exists():
            for line in packed_refs_file.read_text(encoding="utf-8").splitlines():
                if line.endswith(ref_path):
                    return line.split()[0].strip()
        return "0000000000000000000000000000000000000000"
    return head_content


def classify_and_select_files(instruction: str, requested_files: list[str] | None = None) -> list[str]:
    """Selects the minimal relevant set of memory files based on task intent and keywords."""
    selected = list(ALWAYS_CONSULTED_FILES)

    if requested_files:
        for rf in requested_files:
            if rf in ALLOWED_MEMORY_FILES and rf not in selected:
                selected.append(rf)
        return selected

    inst_lower = instruction.lower()

    # Keyword mappings to relevant detail files
    keyword_rules = [
        ("BACKLOG.md", ["backlog", "priority", "safe next", "next area", "next task", "next step", "open work", "highest-priority", "todo"]),
        ("TECHNICAL_CONTEXT.md", ["technical", "architecture", "stack", "tooling", "scripts", "integration", "pipeline", "schema", "bridge", "dispatcher", "video", "h.264"]),
        ("DECISIONS.md", ["decision", "supersede", "policy", "principle", "framework", "d-00"]),
        ("PRODUCT_VISION.md", ["vision", "product", "strategy", "revenue", "monetization", "scope boundary", "goal"]),
        ("OPEN_QUESTIONS.md", ["question", "unknown", "conflict", "gap", "clarification", "ambiguity"]),
        ("LESSONS_LEARNED.md", ["lesson", "learned", "mistake", "retrospective", "avoid"]),
        ("SOURCE_INDEX.md", ["source", "provenance", "origin", "index", "audit trail"]),
        ("IDEA_ARCHIVE.md", ["idea", "archive", "future idea", "brainstorm", "concept"]),
        ("MEMORY_CHANGELOG.md", ["changelog", "history", "version history", "migration"]),
    ]

    for filename, keywords in keyword_rules:
        if any(kw in inst_lower for kw in keywords):
            if filename not in selected:
                selected.append(filename)

    return selected


def redact_sensitive_content(text: str) -> str:
    """Scans and redacts any potential token or credential pattern."""
    redacted = text
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub("[REDACTED_CREDENTIAL]", redacted)
    return redacted


def extract_status_labels(content: str) -> list[str]:
    """Extracts all recognized status labels present in the consulted text."""
    matches = STATUS_LABEL_PATTERN.findall(content)
    seen = set()
    ordered = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            ordered.append(m)
    return ordered


def extract_key_sections(filename: str, content: str) -> dict:
    """Extracts structured summary and high-signal sections from a memory markdown file."""
    lines = content.splitlines()
    sections = {}
    current_header = "Overview"
    current_lines = []

    for line in lines:
        if line.startswith("#"):
            if current_lines:
                sections[current_header] = "\n".join(current_lines).strip()
            current_header = line.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections[current_header] = "\n".join(current_lines).strip()

    return sections


def build_memory_context_package(
    memory_repo_path: Path = DEFAULT_MEMORY_REPO_PATH,
    instruction: str = "",
    requested_files: list[str] | None = None,
) -> dict:
    """Constructs a deterministic, validated Memory Context Package."""
    if not memory_repo_path.exists():
        fail(f"Memory repository path does not exist: {memory_repo_path}")

    memory_commit = get_memory_commit(memory_repo_path)
    files_to_consult = classify_and_select_files(instruction, requested_files)

    all_status_labels = set()
    source_references = []
    relevant_context = {
        "instruction_analyzed": instruction,
        "consulted_files_count": len(files_to_consult),
        "file_extracts": {},
    }

    for fname in files_to_consult:
        fpath = memory_repo_path / fname
        if not fpath.exists():
            continue

        raw_content = fpath.read_text(encoding="utf-8")
        clean_content = redact_sensitive_content(raw_content)

        labels = extract_status_labels(clean_content)
        all_status_labels.update(labels)
        source_references.append(fname)

        sections = extract_key_sections(fname, clean_content)
        relevant_context["file_extracts"][fname] = {
            "status_labels_found": labels,
            "sections": sections,
        }

    # Ensure canonical status label order
    canonical_labels = [
        "VERIFIED_CURRENT",
        "EXTERNAL_STATUS",
        "HISTORICAL_DECISION",
        "PLANNED",
        "IDEA",
        "CONFLICT",
        "UNKNOWN",
        "STATUS_BOUNDARY",
        "PAUSED",
        "PAUSED_EXTERNAL_GATE",
        "DEFERRED",
        "NOT VERIFIED",
        "IN PROGRESS",
    ]
    ordered_labels = [l for l in canonical_labels if l in all_status_labels]

    context_package = {
        "memory_repo": DEFAULT_MEMORY_REPO_NAME,
        "memory_commit": memory_commit,
        "files_consulted": files_to_consult,
        "relevant_context": relevant_context,
        "status_labels": ordered_labels,
        "source_references": source_references,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    return context_package


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve read-only Project Memory Context Package for Courier")
    parser.add_argument("--memory-repo", default=str(DEFAULT_MEMORY_REPO_PATH), help="Path to 2026-project-memory")
    parser.add_argument("--instruction", default="", help="Instruction string to analyze for relevant context")
    parser.add_argument("--files", nargs="*", help="Explicit list of files to consult")
    parser.add_argument("--output", help="Optional output JSON file path")
    args = parser.parse_args()

    repo_path = Path(args.memory_repo).resolve()
    package = build_memory_context_package(
        memory_repo_path=repo_path,
        instruction=args.instruction,
        requested_files=args.files,
    )

    out_json = json.dumps(package, indent=2)
    if args.output:
        out_file = Path(args.output)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(out_json + "\n", encoding="utf-8")
        print(f"MEMORY_CONTEXT_PACKAGE_WRITTEN: {out_file}")
    else:
        print(out_json)


if __name__ == "__main__":
    main()
