"""Repo Reality Check: a local markdown report for one checkout.

The scan reads files on disk. It does not execute customer code. Pytest pass,
fail, and skip counts are taken only from an optional pytest-json-report file
the caller already produced. ``--github`` downloads one public tarball first
(see repo_reality_fetch); a local directory scan does not use the network.

CLI: python -m courier_core.repo_reality_report <repo_path> [--pytest-json FILE] [--out report.md]
     python -m courier_core.repo_reality_report --github owner/repo[@ref] [--out report.md]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

from courier_core.repo_reality_fetch import FetchError, fetch_public

MAX_FILES = 5000
MAX_FILE_READ_BYTES = 256 * 1024
LARGEST_LIMIT = 10
MARKER_FILE_LIMIT = 10
LIST_LIMIT = 30
ONE_MB = 1024 * 1024
FIXTURE_SECRET_POINTS = 2
MARKER_HYGIENE_FLOOR = 5

SKIP_DIR_NAMES = frozenset(
    {
        ".cache",
        ".eggs",
        ".env",
        ".git",
        ".gradle",
        ".mypy_cache",
        ".next",
        ".nuxt",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        ".virtualenv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "env",
        "htmlcov",
        "node_modules",
        "site-packages",
        "target",
        "vendor",
        "venv",
        "virtualenv",
    }
)

EXT_LANGUAGE = {
    ".bash": "Shell",
    ".c": "C",
    ".cc": "C++",
    ".cfg": "INI",
    ".cpp": "C++",
    ".cs": "C#",
    ".css": "CSS",
    ".go": "Go",
    ".h": "C",
    ".hpp": "C++",
    ".html": "HTML",
    ".ini": "INI",
    ".java": "Java",
    ".js": "JavaScript",
    ".json": "JSON",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".md": "Markdown",
    ".php": "PHP",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".rst": "reStructuredText",
    ".scss": "SCSS",
    ".sh": "Shell",
    ".sql": "SQL",
    ".swift": "Swift",
    ".toml": "TOML",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".txt": "Text",
    ".xml": "XML",
    ".yaml": "YAML",
    ".yml": "YAML",
}

# Component id, weight, rule. Weights sum to 100.
WEIGHTS: tuple[tuple[str, int, str], ...] = (
    ("readme", 10, "README file at the checkout root"),
    ("license", 5, "LICENSE file at the checkout root"),
    ("gitignore", 8, ".gitignore at the checkout root"),
    ("test_files", 12, "at least one test file"),
    ("test_functions", 8, "at least one test function"),
    ("ci_config", 10, "at least one CI config"),
    ("ci_jobs", 5, "at least one CI job"),
    ("manifest", 8, "at least one dependency manifest"),
    ("pinning", 14, "share of parsed dependencies with an exact version pin"),
    ("markers", 10, "one point off per 5 TODO, FIXME, or HACK markers, floor 0"),
    ("secrets", 10, "production secrets-risk hits score 0; hits only in tests, fixtures, or docs cost 2"),
)

PYTEST_FAIL_POINTS = 3
PYTEST_FAIL_CAP = 15
PYTEST_JSON_POINTS = 5

COMPONENT_LABELS = {
    "readme": "README",
    "license": "LICENSE",
    "gitignore": ".gitignore",
    "test_files": "Test files",
    "test_functions": "Test functions",
    "ci_config": "CI config",
    "ci_jobs": "CI jobs",
    "manifest": "Dependency manifest",
    "pinning": "Pinned dependencies",
    "markers": "Marker hygiene",
    "secrets": "Secrets-risk hygiene",
}

_PY_TEST_NAME = re.compile(r"^(?:test_.+\.py|.+_test\.py)$", re.IGNORECASE)
_JS_TEST_NAME = re.compile(r"^.+\.(?:test|spec)\.(?:js|jsx|ts|tsx|mjs|cjs)$", re.IGNORECASE)
_GO_TEST_NAME = re.compile(r"^.+_test\.go$", re.IGNORECASE)
_TEST_DIR_NAMES = frozenset({"test", "tests", "__tests__"})
_PY_FUNC = re.compile(r"(?m)^[ \t]*(?:async[ \t]+def|def)[ \t]+test_[A-Za-z0-9_]*")
_JS_FUNC = re.compile(r"(?m)^[ \t]*(?:it|test)[ \t]*\(")
_GO_FUNC = re.compile(r"(?m)^func[ \t]+Test[A-Za-z0-9_]*[ \t]*\(")
_TODO = re.compile(r"\bTODO\b")
_FIXME = re.compile(r"\bFIXME\b")
_HACK = re.compile(r"\bHACK\b")

# Patterns store a name only. Callers count matches and discard the text.
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("assigned_secret", re.compile(
        r"(?i)\b(?:api[_-]?key|passwd|password|secret|token)\b\s*[=:]\s*['\"][^'\"]{12,200}['\"]"
    )),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,80}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,80}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]{0,20}PRIVATE KEY-----")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,80}\b")),
)

_README_NAMES = frozenset(
    {"readme", "readme.md", "readme.rst", "readme.txt", "readme.markdown", "readme.mdown"}
)
_LICENSE_NAMES = frozenset(
    {
        "license",
        "license.md",
        "license.rst",
        "license.txt",
        "licence",
        "licence.md",
        "licence.rst",
        "licence.txt",
        "copying",
        "copying.md",
        "copying.txt",
    }
)
_LOCKFILE_NAMES = frozenset(
    {
        "cargo.lock",
        "composer.lock",
        "gemfile.lock",
        "go.sum",
        "package-lock.json",
        "pipfile.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "uv.lock",
        "yarn.lock",
    }
)
_GITLAB_RESERVED = frozenset(
    {"default", "include", "spec", "stages", "variables", "workflow"}
)
_NPM_EXACT = re.compile(r"v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\Z")
_HELPER_NAME = re.compile(
    r"(?i)^(?:conftest|(?:_?fakes?)|(?:_?builders?))(?:\.[A-Za-z0-9]+)?$"
)
_DOC_NAME = re.compile(
    r"(?i)^(?:readme|changelog|changes|contributing|authors|history)(?:\.[A-Za-z0-9]+)?$"
)
_NON_PROD_DIRS = frozenset(
    {
        "__fixtures__",
        "__tests__",
        "doc",
        "docs",
        "documentation",
        "fixture",
        "fixtures",
        "test",
        "testdata",
        "tests",
    }
)
_HELPER_DIRS = frozenset({"builder", "builders", "fake", "fakes", "_fake", "_fakes"})
_SCRATCH_DIR_NAMES = frozenset({"attic", "scratch", "scratches", "scratchpad"})
_BINARY_ARCHIVE_EXTS = frozenset(
    {
        ".7z",
        ".a",
        ".apk",
        ".bin",
        ".bz2",
        ".class",
        ".deb",
        ".dll",
        ".dmg",
        ".exe",
        ".gz",
        ".iso",
        ".jar",
        ".lib",
        ".msi",
        ".o",
        ".obj",
        ".pyc",
        ".rar",
        ".rpm",
        ".so",
        ".tar",
        ".tgz",
        ".war",
        ".wasm",
        ".whl",
        ".xz",
        ".zip",
    }
)
_LARGE_DATA_EXTS = frozenset({".json", ".jsonl", ".ndjson"})

assert sum(weight for _, weight, _ in WEIGHTS) == 100
_WEIGHT = {key: weight for key, weight, _rule in WEIGHTS}


def build_report(
    repo_path: Path | str,
    pytest_json: Path | str | None = None,
    evidence: dict | None = None,
) -> str:
    """Return the markdown report. Never includes matched secret text."""
    return render_markdown(analyze(repo_path, pytest_json), evidence)


def analyze(repo_path: Path | str, pytest_json: Path | str | None = None) -> dict:
    """Scan ``repo_path`` and return a JSON-ready summary. Paths are relative."""
    root = Path(repo_path)
    files, capped, scratch_dirs = _walk(root)
    languages: dict[str, list[int]] = {}
    other_exts: set[str] = set()
    test_rows: list[dict] = []
    helper_rows: list[str] = []
    stray_rows: list[dict] = []
    test_functions = 0
    marker_rows: list[dict] = []
    marker_totals = {"todo": 0, "fixme": 0, "hack": 0}
    ci_rows: list[dict] = []
    manifest_rows: list[dict] = []
    largest: list[dict] = []
    large_binaries: list[dict] = []
    large_json: list[dict] = []
    secret_files: dict[str, dict[str, int]] = {}
    secret_patterns: dict[str, int] = {}
    project = {
        "readme": {"present": False, "path": None},
        "license": {"present": False, "path": None},
        "gitignore": {"present": False, "path": None},
    }
    total_lines = 0
    partial_files = 0

    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            size = path.stat().st_size
        except OSError:
            continue
        blob, binary, truncated = _read_prefix(path)
        line_count = 0 if binary else _line_count(blob)
        if truncated:
            partial_files += 1
        if not binary:
            total_lines += line_count
        lang, other_ext = _language(path.name)
        if other_ext:
            other_exts.add(other_ext)
        bucket = languages.setdefault(lang, [0, 0])
        bucket[0] += 1
        bucket[1] += 0 if binary else line_count
        suffix = Path(path.name).suffix.lower()
        if size > ONE_MB and suffix in _BINARY_ARCHIVE_EXTS:
            large_binaries.append({"path": rel, "bytes": size})
        if size > ONE_MB and suffix in _LARGE_DATA_EXTS:
            large_json.append({"path": rel, "bytes": size})
        largest.append(
            {
                "path": rel,
                "bytes": size,
                "lines": None if binary else line_count,
                "binary": binary,
                "partial": truncated and not binary,
            }
        )
        text = "" if binary else blob.decode("utf-8", errors="replace")
        funcs = 0 if binary else _count_test_functions(path.name, text)
        if is_test_file(rel, funcs):
            test_functions += funcs
            test_rows.append({"path": rel, "functions": funcs})
        elif _is_helper_file(rel):
            helper_rows.append(rel)
        if _is_stray_test(rel):
            stray_rows.append({"path": rel, "functions": funcs})
        if text:
            todo, fixme, hack = len(_TODO.findall(text)), len(_FIXME.findall(text)), len(_HACK.findall(text))
            if todo or fixme or hack:
                marker_totals["todo"] += todo
                marker_totals["fixme"] += fixme
                marker_totals["hack"] += hack
                marker_rows.append(
                    {"path": rel, "todo": todo, "fixme": fixme, "hack": hack, "total": todo + fixme + hack}
                )
            bucket_name = _secret_bucket(rel)
            for pattern_name, hits in _secret_hits(text).items():
                secret_patterns[pattern_name] = secret_patterns.get(pattern_name, 0) + hits
                file_bucket = secret_files.setdefault(rel, {"hits": 0, "bucket": bucket_name})
                file_bucket["hits"] += hits
        if "/" not in rel:
            _note_project_file(project, rel)
        kind = _ci_kind(rel)
        if kind:
            ci_rows.append({"kind": kind, "path": rel, "jobs": _count_jobs(kind, text)})
        manifest_kind = _manifest_kind(rel)
        if manifest_kind:
            pinned, unpinned, note = _count_dependencies(manifest_kind, text)
            if truncated:
                note = (note + "; " if note else "") + "prefix only"
            manifest_rows.append(
                {
                    "path": rel,
                    "kind": manifest_kind,
                    "pinned": pinned,
                    "unpinned": unpinned,
                    "note": note,
                    "in_ratio": _in_pin_ratio(manifest_kind, note),
                }
            )

    language_rows = _collapse_languages(languages, other_exts)
    test_rows.sort(key=lambda row: row["path"])
    helper_rows.sort()
    stray_rows.sort(key=lambda row: row["path"])
    marker_rows.sort(key=lambda row: (-row["total"], row["path"]))
    ci_rows.sort(key=lambda row: (row["kind"], row["path"]))
    manifest_rows.sort(key=lambda row: row["path"])
    largest.sort(key=lambda row: (-row["bytes"], row["path"]))
    large_binaries.sort(key=lambda row: (-row["bytes"], row["path"]))
    large_json.sort(key=lambda row: (-row["bytes"], row["path"]))
    secret_file_rows = [
        {"path": path, "hits": info["hits"], "bucket": info["bucket"]}
        for path, info in secret_files.items()
    ]
    secret_file_rows.sort(key=lambda row: row["path"])
    production_rows = [row for row in secret_file_rows if row["bucket"] == "production"]
    non_production_rows = [row for row in secret_file_rows if row["bucket"] != "production"]
    secret_pattern_rows = [
        {"pattern": name, "hits": hits} for name, hits in secret_patterns.items()
    ]
    secret_pattern_rows.sort(key=lambda row: row["pattern"])

    ratio_pinned = sum(row["pinned"] for row in manifest_rows if row["in_ratio"])
    ratio_unpinned = sum(row["unpinned"] for row in manifest_rows if row["in_ratio"])
    parsed_manifests = sum(1 for row in manifest_rows if row["in_ratio"])
    pytest_info = _parse_pytest(None if pytest_json is None else Path(pytest_json))
    summary = {
        "files": len(largest),
        "lines": total_lines,
        "lines_partial_files": partial_files,
        "scan_capped": capped,
        "languages": language_rows,
        "test_files": len(test_rows),
        "test_functions": test_functions,
        "test_file_rows": test_rows,
        "test_helpers": helper_rows,
        "pytest": pytest_info,
        "markers": {
            "todo": marker_totals["todo"],
            "fixme": marker_totals["fixme"],
            "hack": marker_totals["hack"],
            "total": marker_totals["todo"] + marker_totals["fixme"] + marker_totals["hack"],
            "top_files": marker_rows[:MARKER_FILE_LIMIT],
        },
        "ci": {
            "configs": len(ci_rows),
            "jobs": sum(row["jobs"] for row in ci_rows),
            "rows": ci_rows,
        },
        "project_files": project,
        "dependencies": {
            "manifests": len(manifest_rows),
            "pinned": sum(row["pinned"] for row in manifest_rows),
            "unpinned": sum(row["unpinned"] for row in manifest_rows),
            "ratio_pinned": ratio_pinned,
            "ratio_unpinned": ratio_unpinned,
            "parsed_manifests": parsed_manifests,
            "rows": manifest_rows,
        },
        "largest": largest[:LARGEST_LIMIT],
        "secrets": {
            "files": len(secret_file_rows),
            "hits": sum(row["hits"] for row in secret_file_rows),
            "file_rows": secret_file_rows,
            "pattern_rows": secret_pattern_rows,
            "production_files": len(production_rows),
            "production_hits": sum(row["hits"] for row in production_rows),
            "production_rows": production_rows,
            "non_production_files": len(non_production_rows),
            "non_production_hits": sum(row["hits"] for row in non_production_rows),
            "non_production_rows": non_production_rows,
        },
        "hygiene": {
            "large_binaries": large_binaries,
            "scratch_dirs": scratch_dirs,
            "large_json": large_json,
            "stray_tests": stray_rows,
        },
        "limits": _limits(),
    }
    summary["hygiene"]["flags"] = _hygiene_flags(summary)
    summary["score"] = _score(summary)
    summary["ampel"] = _ampel(summary)
    summary["summary_sentences"] = _summary_sentences(summary)
    summary["next_steps"] = _next_steps(summary)
    return summary


def render_markdown(data: dict, evidence: dict | None = None) -> str:
    """Render ``analyze`` output. The text contains counts and paths only."""
    lines: list[str] = ["# Repo Reality Check", ""]
    if evidence:
        lines.append(
            "Read-only scan of a public GitHub tarball. Customer code was not executed. "
            "Pytest counts are included only when a pytest JSON file is supplied."
        )
        lines.append("")
        lines.append(f"- Source: {evidence['source']}")
        lines.append(f"- Commit: {evidence['sha']}")
        lines.append(f"- Tarball sha256: {evidence['tarball_sha256']}")
        lines.append("")
    else:
        lines.append(
            "Read-only scan of one local checkout. No network calls. Customer code was not executed. "
            "Pytest counts are included only when a pytest JSON file is supplied."
        )
        lines.append("")
    lines.extend(_render_summary(data))
    lines.extend(_heading("Repositorygröße", "Repository size"))
    lines.append(f"- Files: {data['files']}")
    lines.append(f"- Lines: {data['lines']}")
    if data["lines_partial_files"]:
        lines.append(
            f"- Files read only up to the byte cap: {data['lines_partial_files']}"
        )
    if data["scan_capped"]:
        lines.append(f"- File cap hit: counted the first {data['files']} files in sorted walk order")
    lines.append("")
    if data["languages"]:
        lines.extend(
            _table(
                ["Language", "Files", "Lines"],
                [[row["name"], row["files"], row["lines"]] for row in data["languages"]],
            )
        )
    else:
        lines.append("No files.")
    lines.append("")

    lines.extend(_heading("Testdateien", "Test files (static scan)"))
    lines.append(f"- Test files: {data['test_files']}")
    lines.append(f"- Test functions: {data['test_functions']}")
    lines.append(f"- Test-Hilfsdateien: {len(data['test_helpers'])}")
    lines.append("")
    shown, extra = _cap(data["test_file_rows"], LIST_LIMIT)
    if shown:
        lines.extend(_table(["File", "Test functions"], [[row["path"], row["functions"]] for row in shown]))
        if extra:
            lines.append(f"Showing {len(shown)} of {data['test_files']} test files.")
    else:
        lines.append("No test files.")
    lines.append("")
    lines.extend(_heading_level(3, "Test-Hilfsdateien", "Test helper files"))
    helpers, helper_extra = _cap(data["test_helpers"], LIST_LIMIT)
    if helpers:
        lines.extend(_table(["File"], [[path] for path in helpers]))
        if helper_extra:
            lines.append(f"Showing {len(helpers)} of {len(data['test_helpers'])} test helper files.")
    else:
        lines.append("No test helper files.")
    lines.append("")

    lines.extend(_heading("Testergebnisse", "Pytest results (pytest-json-report)"))
    lines.extend(_pytest_lines(data["pytest"]))
    lines.append("")

    markers = data["markers"]
    lines.extend(_heading("Offene Marker", "TODO, FIXME, and HACK"))
    lines.append(f"- TODO: {markers['todo']}")
    lines.append(f"- FIXME: {markers['fixme']}")
    lines.append(f"- HACK: {markers['hack']}")
    lines.append(f"- Total: {markers['total']}")
    lines.append("")
    if markers["top_files"]:
        lines.extend(
            _table(
                ["File", "TODO", "FIXME", "HACK", "Total"],
                [
                    [row["path"], row["todo"], row["fixme"], row["hack"], row["total"]]
                    for row in markers["top_files"]
                ],
            )
        )
    else:
        lines.append("No markers.")
    lines.append("")

    ci = data["ci"]
    lines.extend(_heading("CI-Konfiguration", "Continuous integration"))
    lines.append(f"- Configs: {ci['configs']}")
    lines.append(f"- Jobs: {ci['jobs']}")
    lines.append("")
    if ci["rows"]:
        lines.extend(
            _table(
                ["Kind", "File", "Jobs"],
                [[row["kind"], row["path"], row["jobs"]] for row in ci["rows"]],
            )
        )
    else:
        lines.append("No CI config found.")
    lines.append("")

    lines.extend(_heading("Projektdateien", "README, LICENSE, and gitignore"))
    for key, label in (("readme", "README"), ("license", "LICENSE"), ("gitignore", ".gitignore")):
        item = data["project_files"][key]
        if item["present"]:
            lines.append(f"- {label}: present ({item['path']})")
        else:
            lines.append(f"- {label}: absent")
    lines.append("")

    deps = data["dependencies"]
    lines.extend(_heading("Abhängigkeiten", "Dependency manifests"))
    lines.append(f"- Manifests: {deps['manifests']}")
    lines.append(f"- Unpinned dependencies: {deps['unpinned']}")
    lines.append(f"- Pinned dependencies: {deps['pinned']}")
    lines.append(
        "- Pin rule: requirements and PEP 621 count as pinned with `==` or `===`; "
        "package.json counts a bare major.minor.patch; Poetry, Cargo, and Composer count a leading `=`."
    )
    lines.append("")
    if deps["rows"]:
        lines.extend(
            _table(
                ["Manifest", "Kind", "Pinned", "Unpinned", "Note"],
                [
                    [row["path"], row["kind"], row["pinned"], row["unpinned"], row["note"] or "-"]
                    for row in deps["rows"]
                ],
            )
        )
    else:
        lines.append("No dependency manifest found.")
    lines.append("")

    lines.extend(_heading("Größte Dateien", "Largest files"))
    if data["largest"]:
        rows = []
        for row in data["largest"]:
            if row["binary"]:
                shown_lines = "binary"
            elif row["partial"]:
                shown_lines = f"{row['lines']} (prefix)"
            else:
                shown_lines = row["lines"]
            rows.append([row["bytes"], shown_lines, row["path"]])
        lines.extend(_table(["Bytes", "Lines", "File"], rows))
    else:
        lines.append("No files.")
    lines.append("")

    lines.extend(_render_secrets(data["secrets"]))
    lines.extend(_render_hygiene(data))

    score = data["score"]
    lines.extend(_heading("Realitätswert", "Reality score"))
    lines.append(f"Score: {score['value']} / 100")
    lines.append("")
    lines.append(
        f"Formula: {score['awarded']} awarded - {score['deducted']} deducted = {score['raw']}, "
        f"clamped to {score['value']}."
    )
    lines.append("")
    lines.extend(
        _table(
            ["Component", "Weight", "Awarded", "Rule", "Observation"],
            [
                [row["label"], row["weight"], row["awarded"], row["rule"], row["observation"]]
                for row in score["components"]
            ],
        )
    )
    lines.append("")
    lines.extend(
        _table(
            ["Deduction", "Points", "Rule", "Observation"],
            [
                [row["label"], row["points"], row["rule"], row["observation"]]
                for row in score["deductions"]
            ],
        )
    )
    lines.append("")

    lines.extend(_heading("Nächste fünf Schritte", "Top 5 next steps"))
    for index, step in enumerate(data["next_steps"], start=1):
        lines.append(f"{index}. {step}")
    lines.append("")

    limits = data["limits"]
    lines.extend(_heading("Grenzen", "Limits"))
    lines.append(f"- Max files: {limits['max_files']}")
    lines.append(f"- Max bytes read per file: {limits['max_file_read_bytes']}")
    lines.append("- Symlinks are skipped.")
    lines.append("- Directories skipped: " + ", ".join(f"`{name}`" for name in limits["skip_dirs"]))
    lines.append(
        "- A test file matches test_*.py, *_test.py, *.test.js, *.spec.js, or *_test.go, and either contains at least one test function or lives under test, tests, or __tests__."
    )
    lines.append(
        "- Test-Hilfsdateien are conftest.py anywhere, plus fake/fakes and builder/builders files under a test directory. They are not test files."
    )
    lines.append(
        "- Stray tests are test-named files at the checkout root or under scripts/. They are a hygiene finding."
    )
    lines.append("- Test files and test functions are counted with text patterns. Files are not imported.")
    lines.append("- Marker words are the uppercase tokens TODO, FIXME, and HACK.")
    lines.append("- Pytest is not run. Pass, fail, and skip come from the optional JSON file.")
    lines.append(
        "- Secrets-risk hits in tests, fixtures, docs, test-named files, or doc names such as README cost 2 points. Production hits set that component to 0. Match text is discarded."
    )
    lines.append(
        f"- Binaries and archives over {ONE_MB} bytes, and JSON, JSONL, or NDJSON over {ONE_MB} bytes, are hygiene findings."
    )
    lines.append(
        "- Scratch directory names: attic, scratch, scratches, scratchpad."
    )
    lines.append(
        "- Ampel Tests: Rot when test files or test functions are 0; Grün when both are positive and pytest JSON has 0 failed and 0 errors; otherwise Gelb."
    )
    lines.append(
        "- Ampel CI: Rot at 0 configs; Gelb when configs exist and jobs are 0; Grün when jobs are positive."
    )
    lines.append(
        "- Ampel Abhängigkeiten: Rot at 0 manifests; Grün when every parsed dependency is pinned; otherwise Gelb."
    )
    lines.append(
        "- Ampel Geheimnis-Risiko: Rot when production hits are positive; Gelb when only tests, fixtures, or docs have hits; Grün at 0 hits."
    )
    lines.append(
        "- Ampel Repo-Hygiene: Rot when a large binary/archive, a large JSON/JSONL file, or a scratch/attic directory is present, or when 3 or more hygiene flags are set; Gelb for 1 or 2 other flags; Grün at 0 flags. Flags: missing README, LICENSE, or .gitignore; 5 or more markers; large binaries; large JSON/JSONL; scratch/attic; stray tests."
    )
    lines.append("- A score is a sum of the weights above. It is not a security verdict.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m courier_core.repo_reality_report",
        description="Write a local Repo Reality Check markdown report.",
    )
    parser.add_argument("repo_path", nargs="?", default=None, help="local checkout directory")
    parser.add_argument("--github", default=None, help="public owner/repo or owner/repo@ref")
    parser.add_argument("--pytest-json", default=None, help="pytest-json-report file")
    parser.add_argument("--out", default=None, help="write the report here instead of stdout")
    args = parser.parse_args(argv)
    if args.github and args.repo_path:
        print("pass either a local directory or --github, not both", file=sys.stderr)
        return 2
    if args.github:
        try:
            report = _report_from_github(args.github, args.pytest_json)
        except FetchError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    elif args.repo_path:
        repo = Path(args.repo_path)
        if not repo.is_dir():
            print("repo path is not a directory", file=sys.stderr)
            return 2
        report = build_report(repo, args.pytest_json)
    else:
        print("pass a local directory or --github owner/repo[@ref]", file=sys.stderr)
        return 2
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        return 0
    sys.stdout.write(report)
    return 0


def _report_from_github(spec: str, pytest_json: str | None) -> str:
    fetched = fetch_public(spec)
    try:
        evidence = {
            "source": f"github.com/{fetched.owner}/{fetched.repo}@{fetched.ref}",
            "sha": fetched.sha,
            "tarball_sha256": fetched.tarball_sha256,
        }
        return build_report(fetched.root, pytest_json, evidence)
    finally:
        shutil.rmtree(fetched.temp_dir, ignore_errors=True)


def is_test_file(rel: str, function_count: int = 0) -> bool:
    """A test-named file counts when it has a test function, or it lives under a tests directory."""
    name = rel.rsplit("/", 1)[-1]
    if not _test_name_match(name):
        return False
    if function_count >= 1:
        return True
    return _under_test_dir(rel)


def _test_name_match(name: str) -> bool:
    return bool(_PY_TEST_NAME.match(name) or _JS_TEST_NAME.match(name) or _GO_TEST_NAME.match(name))


def _under_test_dir(rel: str) -> bool:
    parents = [part.lower() for part in rel.split("/")[:-1]]
    return any(part in _TEST_DIR_NAMES for part in parents)


def _is_helper_file(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    parents = [part.lower() for part in rel.split("/")[:-1]]
    if name.lower() == "conftest.py":
        return True
    if not _under_test_dir(rel):
        return False
    if _HELPER_NAME.match(name):
        return True
    return any(part in _HELPER_DIRS for part in parents)


def _is_stray_test(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    if not _test_name_match(name) or _under_test_dir(rel):
        return False
    if "/" not in rel:
        return True
    return rel.split("/", 1)[0].lower() == "scripts"


def _secret_bucket(rel: str) -> str:
    if _non_production_path(rel):
        return "non_production"
    return "production"


def _non_production_path(rel: str) -> bool:
    parts = rel.split("/")
    name = parts[-1]
    parents = [part.lower() for part in parts[:-1]]
    if any(part in _NON_PROD_DIRS for part in parents):
        return True
    if _test_name_match(name) or _HELPER_NAME.match(name) or _DOC_NAME.match(name):
        return True
    return False


def _walk(root: Path) -> tuple[list[Path], bool, list[str]]:
    found: list[Path] = []
    scratch: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel_parent = Path(dirpath).relative_to(root)
        parent_posix = "" if rel_parent == Path(".") else rel_parent.as_posix()
        kept: list[str] = []
        for name in sorted(dirnames):
            if name in SKIP_DIR_NAMES or name.endswith(".egg-info"):
                continue
            if (Path(dirpath) / name).is_symlink():
                continue
            if name.lower() in _SCRATCH_DIR_NAMES:
                scratch.append(f"{parent_posix}/{name}" if parent_posix else name)
            kept.append(name)
        dirnames[:] = kept
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.is_symlink() or not path.is_file():
                continue
            found.append(path)
            if len(found) >= MAX_FILES:
                return found, True, sorted(set(scratch))
    return found, False, sorted(set(scratch))


def _read_prefix(path: Path) -> tuple[bytes, bool, bool]:
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            blob = handle.read(MAX_FILE_READ_BYTES + 1)
    except OSError:
        return b"", False, False
    truncated = len(blob) > MAX_FILE_READ_BYTES or size > MAX_FILE_READ_BYTES
    blob = blob[:MAX_FILE_READ_BYTES]
    return blob, b"\0" in blob[:8192], truncated


def _line_count(blob: bytes) -> int:
    if not blob:
        return 0
    lines = blob.count(b"\n")
    if not blob.endswith(b"\n"):
        lines += 1
    return lines


def _language(filename: str) -> tuple[str, str | None]:
    suffix = Path(filename).suffix.lower()
    if not suffix:
        return "no extension", None
    named = EXT_LANGUAGE.get(suffix)
    if named:
        return named, None
    return "Sonstige", suffix


def _collapse_languages(languages: dict[str, list[int]], other_exts: set[str]) -> list[dict]:
    rows = [
        {"name": name, "files": counts[0], "lines": counts[1]}
        for name, counts in languages.items()
        if name != "Sonstige"
    ]
    rows.sort(key=lambda row: row["name"])
    if "Sonstige" in languages:
        counts = languages["Sonstige"]
        rows.append(
            {
                "name": f"Sonstige ({len(other_exts)})",
                "files": counts[0],
                "lines": counts[1],
            }
        )
    return rows


def _count_test_functions(filename: str, text: str) -> int:
    lower = filename.lower()
    if lower.endswith(".py"):
        return len(_PY_FUNC.findall(text))
    if lower.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")):
        return len(_JS_FUNC.findall(text))
    if lower.endswith(".go"):
        return len(_GO_FUNC.findall(text))
    return 0


def _secret_hits(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name, pattern in _SECRET_PATTERNS:
        hits = sum(1 for _match in pattern.finditer(text))
        if hits:
            counts[name] = hits
    return counts


def _note_project_file(project: dict, rel: str) -> None:
    lower = rel.lower()
    if project["readme"]["path"] is None and lower in _README_NAMES:
        project["readme"] = {"present": True, "path": rel}
    if project["license"]["path"] is None and lower in _LICENSE_NAMES:
        project["license"] = {"present": True, "path": rel}
    if rel == ".gitignore":
        project["gitignore"] = {"present": True, "path": rel}


def _ci_kind(rel: str) -> str | None:
    name = rel.rsplit("/", 1)[-1]
    if rel.startswith(".github/workflows/") and rel.count("/") == 2 and name.endswith((".yml", ".yaml")):
        return "GitHub Actions"
    if rel == ".gitlab-ci.yml":
        return "GitLab CI"
    if rel == ".circleci/config.yml":
        return "CircleCI"
    if "/" not in rel and name in {"azure-pipelines.yml", "azure-pipelines.yaml"}:
        return "Azure Pipelines"
    if rel == "bitbucket-pipelines.yml":
        return "Bitbucket Pipelines"
    if rel == ".travis.yml":
        return "Travis CI"
    if "/" not in rel and name == "Jenkinsfile":
        return "Jenkins"
    return None


def _count_jobs(kind: str, text: str) -> int:
    if kind in {"GitHub Actions", "CircleCI"}:
        return _mapping_keys(text, "jobs")
    if kind == "GitLab CI":
        return _gitlab_jobs(text)
    if kind == "Azure Pipelines":
        return len(re.findall(r"(?m)^\s*-\s*job\s*:", text))
    if kind == "Bitbucket Pipelines":
        return len(re.findall(r"(?m)^\s*-\s*step\s*:", text))
    if kind == "Travis CI":
        return 1 if text.strip() else 0
    if kind == "Jenkins":
        return len(re.findall(r"\bstage\s*\(", text))
    return 0


def _mapping_keys(text: str, section: str) -> int:
    in_section = False
    count = 0
    for line in text.splitlines():
        if not in_section:
            if re.match(rf"^{re.escape(section)}:\s*(#.*)?$", line):
                in_section = True
            continue
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.match(r"^\S", line):
            break
        if re.match(r"^  [A-Za-z0-9_-]+:", line):
            count += 1
    return count


def _gitlab_jobs(text: str) -> int:
    count = 0
    name: str | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal count
        if name and name not in _GITLAB_RESERVED:
            blob = "\n".join(body)
            if re.search(r"(?m)^  (?:script|trigger|extends):\s*", blob):
                count += 1

    for line in text.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-][A-Za-z0-9_.:/-]*):\s*(#.*)?$", line)
        if match:
            flush()
            name = match.group(1)
            body = []
        else:
            body.append(line)
    flush()
    return count


def _manifest_kind(rel: str) -> str | None:
    name = rel.rsplit("/", 1)[-1]
    lower = name.lower()
    parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
    if lower in _LOCKFILE_NAMES:
        return "lockfile"
    if lower == "requirements.txt" or (lower.startswith("requirements-") and lower.endswith(".txt")):
        return "requirements"
    if lower == "constraints.txt":
        return "requirements"
    if parent == "requirements" and lower.endswith(".txt"):
        return "requirements"
    if lower == "pyproject.toml":
        return "pyproject"
    if lower == "package.json":
        return "package.json"
    if lower == "go.mod":
        return "go.mod"
    if lower == "cargo.toml":
        return "cargo"
    if lower == "gemfile":
        return "gemfile"
    if lower == "composer.json":
        return "composer"
    if lower == "pipfile":
        return "pipfile"
    if lower == "setup.cfg":
        return "setup.cfg"
    return None


def _in_pin_ratio(kind: str, note: str) -> bool:
    if kind == "lockfile":
        return False
    return "could not parse" not in note


def _count_dependencies(kind: str, text: str) -> tuple[int, int, str]:
    if kind == "lockfile":
        return 0, 0, "lockfile"
    if kind == "requirements":
        return (*_parse_requirements(text), "")
    if kind == "pyproject":
        return (*_parse_pyproject(text), "")
    if kind == "package.json":
        return _parse_package_json(text)
    if kind == "go.mod":
        return (*_parse_gomod(text), "")
    if kind == "cargo":
        return (*_parse_cargo(text), "")
    if kind == "gemfile":
        return (*_parse_gemfile(text), "")
    if kind == "composer":
        return _parse_composer(text)
    if kind == "pipfile":
        return (*_parse_pipfile(text), "")
    if kind == "setup.cfg":
        return (*_parse_setup_cfg(text), "")
    return 0, 0, ""


def _pin_requirement(spec: str) -> bool:
    base = spec.split(";", 1)[0]
    return "==" in base


def _parse_requirements(text: str) -> tuple[int, int]:
    pinned = unpinned = 0
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith(("#", "--")):
            continue
        if line.startswith("-r ") or line.startswith("-c ") or line.startswith("-f "):
            continue
        if line.startswith("-e ") or line.startswith("--editable"):
            unpinned += 1
            continue
        if line.startswith("-"):
            continue
        if _pin_requirement(line):
            pinned += 1
        else:
            unpinned += 1
    return pinned, unpinned


def _quoted(line: str) -> list[str]:
    return re.findall(r"""['"]([^'"]+)['"]""", line)


def _parse_pyproject(text: str) -> tuple[int, int]:
    pinned = unpinned = 0
    section = ""
    in_array = False

    def consume(line: str) -> None:
        nonlocal pinned, unpinned
        for spec in _quoted(line):
            if spec.startswith(("http://", "https://")):
                unpinned += 1
                continue
            if _pin_requirement(spec):
                pinned += 1
            else:
                unpinned += 1

    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        header = re.match(r"^\[([^\]]+)\]\s*$", stripped)
        if header:
            section = header.group(1).strip().strip("\"'")
            in_array = False
            continue
        poetry = section in {"tool.poetry.dependencies", "tool.poetry.dev-dependencies"} or (
            section.startswith("tool.poetry.group.") and section.endswith(".dependencies")
        )
        if section == "project" and re.match(r"^dependencies\s*=", stripped):
            consume(stripped)
            after = stripped.split("[", 1)[1] if "[" in stripped else ""
            in_array = "[" in stripped and "]" not in after
            continue
        if section.startswith("project.optional-dependencies"):
            consume(stripped)
            continue
        if in_array:
            consume(stripped)
            if "]" in stripped:
                in_array = False
            continue
        if poetry and not stripped.startswith("python ") and not stripped.startswith("python="):
            match = re.match(r"""^([A-Za-z0-9_.-]+)\s*=\s*['"]([^'"]+)['"]""", stripped)
            if match and match.group(1) != "python":
                spec = match.group(2).strip()
                if spec.startswith("="):
                    pinned += 1
                else:
                    unpinned += 1
                continue
            version = re.match(r"""^version\s*=\s*['"]([^'"]+)['"]""", stripped)
            if version:
                spec = version.group(1).strip()
                if spec.startswith("="):
                    pinned += 1
                else:
                    unpinned += 1
    return pinned, unpinned


def _parse_package_json(text: str) -> tuple[int, int, str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return 0, 0, "could not parse"
    if not isinstance(data, dict):
        return 0, 0, "could not parse"
    pinned = unpinned = 0
    for key in ("dependencies", "devDependencies", "optionalDependencies"):
        table = data.get(key) or {}
        if not isinstance(table, dict):
            continue
        for _name, spec in table.items():
            if _npm_pinned(spec):
                pinned += 1
            else:
                unpinned += 1
    return pinned, unpinned, ""


def _npm_pinned(spec: object) -> bool:
    if not isinstance(spec, str):
        return False
    text = spec.strip()
    if text.startswith("="):
        text = text[1:].strip()
    return _NPM_EXACT.fullmatch(text) is not None


def _parse_gomod(text: str) -> tuple[int, int]:
    pinned = unpinned = 0
    in_block = False
    for raw in text.splitlines():
        stripped = raw.split("//", 1)[0].strip()
        if not stripped:
            continue
        if stripped.startswith("require ("):
            in_block = True
            continue
        if in_block and stripped == ")":
            in_block = False
            continue
        if stripped.startswith("require ") and "(" not in stripped:
            parts = stripped.split()
            if len(parts) >= 3 and parts[2].startswith("v"):
                pinned += 1
            else:
                unpinned += 1
            continue
        if in_block:
            parts = stripped.split()
            if len(parts) >= 2 and parts[1].startswith("v"):
                pinned += 1
            elif parts:
                unpinned += 1
    return pinned, unpinned


def _parse_cargo(text: str) -> tuple[int, int]:
    pinned = unpinned = 0
    section = ""
    interesting = {"dependencies", "dev-dependencies", "build-dependencies"}
    for raw in text.splitlines():
        stripped = raw.strip()
        header = re.match(r"^\[([^\]]+)\]\s*$", stripped)
        if header:
            section = header.group(1).strip()
            continue
        if section not in interesting or not stripped or stripped.startswith("#"):
            continue
        if re.search(r"""=\s*['"]=""", stripped):
            pinned += 1
        elif "=" in stripped:
            unpinned += 1
    return pinned, unpinned


def _parse_gemfile(text: str) -> tuple[int, int]:
    pinned = unpinned = 0
    pattern = re.compile(r"""^\s*gem\s+['"][^'"]+['"]\s*(?:,\s*['"]([^'"]+)['"])?""")
    for raw in text.splitlines():
        match = pattern.match(raw.split("#", 1)[0])
        if not match:
            continue
        spec = match.group(1)
        if spec and not spec.startswith(("~>", ">", "<", "*")):
            pinned += 1
        else:
            unpinned += 1
    return pinned, unpinned


def _parse_composer(text: str) -> tuple[int, int, str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return 0, 0, "could not parse"
    if not isinstance(data, dict):
        return 0, 0, "could not parse"
    pinned = unpinned = 0
    for key in ("require", "require-dev"):
        table = data.get(key) or {}
        if not isinstance(table, dict):
            continue
        for name, spec in table.items():
            if name == "php" or not isinstance(spec, str):
                if name != "php":
                    unpinned += 1
                continue
            body = spec[1:].strip() if spec.startswith("=") else spec
            if _NPM_EXACT.fullmatch(body.lstrip("v")):
                pinned += 1
            else:
                unpinned += 1
    return pinned, unpinned, ""


def _parse_pipfile(text: str) -> tuple[int, int]:
    pinned = unpinned = 0
    section = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        header = re.match(r"^\[([^\]]+)\]\s*$", stripped)
        if header:
            section = header.group(1).strip().strip("\"'")
            continue
        if section not in {"packages", "dev-packages"} or not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"""^[A-Za-z0-9_.-]+\s*=\s*['"]([^'"]+)['"]""", stripped)
        if not match:
            continue
        spec = match.group(1).strip()
        if spec.startswith("=") or "==" in spec:
            pinned += 1
        else:
            unpinned += 1
    return pinned, unpinned


def _parse_setup_cfg(text: str) -> tuple[int, int]:
    pinned = unpinned = 0
    capture = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            capture = False
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in {"install_requires", "tests_require"} and "=" in stripped:
            capture = True
            rest = stripped.split("=", 1)[1].strip()
            if rest:
                for part in rest.split(","):
                    spec = part.strip()
                    if not spec:
                        continue
                    if _pin_requirement(spec):
                        pinned += 1
                    else:
                        unpinned += 1
            continue
        if capture:
            if raw and not raw.startswith((" ", "\t")):
                capture = False
                continue
            spec = stripped.split("#", 1)[0].strip().rstrip(",")
            if not spec:
                continue
            if _pin_requirement(spec):
                pinned += 1
            else:
                unpinned += 1
    return pinned, unpinned


def _parse_pytest(path: Path | None) -> dict:
    empty = {"passed": None, "failed": None, "skipped": None, "errors": None}
    if path is None:
        return {"status": "not_supplied", **empty}
    try:
        if not path.is_file():
            return {"status": "unreadable", **empty}
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {"status": "unreadable", **empty}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"status": "malformed", **empty}
    if not isinstance(data, dict):
        return {"status": "unexpected", **empty}
    summary = data.get("summary")
    tests = data.get("tests")
    if isinstance(summary, dict):
        counts = _summary_counts(summary)
        if counts is None:
            return {"status": "unexpected", **empty}
        return {"status": "ok", **counts}
    if isinstance(tests, list):
        return {"status": "ok", **_count_outcomes(tests)}
    if "summary" in data or "tests" in data:
        return {"status": "unexpected", **empty}
    return {"status": "ok", "passed": 0, "failed": 0, "skipped": 0, "errors": 0}


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _summary_counts(summary: dict) -> dict | None:
    mapping = (("passed", "passed"), ("failed", "failed"), ("skipped", "skipped"), ("errors", "error"))
    counts = {}
    for dest, src in mapping:
        if dest == "errors":
            if "error" in summary:
                raw = summary.get("error")
            elif "errors" in summary:
                raw = summary.get("errors")
            else:
                counts[dest] = 0
                continue
        elif src not in summary:
            counts[dest] = 0
            continue
        else:
            raw = summary.get(src)
        number = _as_int(raw)
        if number is None:
            return None
        counts[dest] = number
    return counts


def _count_outcomes(tests: list) -> dict:
    counts = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    for item in tests:
        if not isinstance(item, dict):
            continue
        outcome = item.get("outcome")
        if outcome == "passed":
            counts["passed"] += 1
        elif outcome == "failed":
            counts["failed"] += 1
        elif outcome == "skipped":
            counts["skipped"] += 1
        elif outcome == "error":
            counts["errors"] += 1
    return counts


def _score(data: dict) -> dict:
    deps = data["dependencies"]
    secrets = data["secrets"]
    observations = {
        "readme": _present_obs(data["project_files"]["readme"]),
        "license": _present_obs(data["project_files"]["license"]),
        "gitignore": _present_obs(data["project_files"]["gitignore"]),
        "test_files": _count_phrase(data["test_files"], "file", "files"),
        "test_functions": _count_phrase(data["test_functions"], "function", "functions"),
        "ci_config": _count_phrase(data["ci"]["configs"], "config", "configs"),
        "ci_jobs": _count_phrase(data["ci"]["jobs"], "job", "jobs"),
        "manifest": _count_phrase(deps["manifests"], "manifest", "manifests"),
        "markers": _count_phrase(data["markers"]["total"], "marker", "markers"),
        "secrets": _secrets_observation(secrets),
    }
    ratio_total = deps["ratio_pinned"] + deps["ratio_unpinned"]
    if ratio_total == 0:
        pin_awarded = 0
        observations["pinning"] = "no parsed dependencies"
    else:
        pin_awarded = (_WEIGHT["pinning"] * deps["ratio_pinned"]) // ratio_total
        observations["pinning"] = f"{deps['ratio_pinned']} pinned of {ratio_total}"
    marker_weight = _WEIGHT["markers"]
    marker_awarded = marker_weight - min(marker_weight, data["markers"]["total"] // 5)
    awarded_for = {
        "readme": _WEIGHT["readme"] if data["project_files"]["readme"]["present"] else 0,
        "license": _WEIGHT["license"] if data["project_files"]["license"]["present"] else 0,
        "gitignore": _WEIGHT["gitignore"] if data["project_files"]["gitignore"]["present"] else 0,
        "test_files": _WEIGHT["test_files"] if data["test_files"] else 0,
        "test_functions": _WEIGHT["test_functions"] if data["test_functions"] else 0,
        "ci_config": _WEIGHT["ci_config"] if data["ci"]["configs"] else 0,
        "ci_jobs": _WEIGHT["ci_jobs"] if data["ci"]["jobs"] else 0,
        "manifest": _WEIGHT["manifest"] if deps["manifests"] else 0,
        "pinning": pin_awarded,
        "markers": marker_awarded,
        "secrets": _secrets_award(secrets),
    }
    components = []
    for key, weight, rule in WEIGHTS:
        components.append(
            {
                "id": key,
                "label": COMPONENT_LABELS[key],
                "weight": weight,
                "awarded": awarded_for[key],
                "rule": rule,
                "observation": observations[key],
            }
        )
    pytest_info = data["pytest"]
    deductions = [_pytest_deductions(pytest_info)]
    awarded = sum(row["awarded"] for row in components)
    deducted = sum(row["points"] for row in deductions)
    raw = awarded - deducted
    value = max(0, min(100, raw))
    return {
        "value": value,
        "awarded": awarded,
        "deducted": deducted,
        "raw": raw,
        "components": components,
        "deductions": deductions,
    }


def _count_phrase(count: int, singular: str, plural: str) -> str:
    word = singular if count == 1 else plural
    return f"{count} {word}"


def _de(count: int, singular: str, plural: str) -> str:
    return _count_phrase(count, singular, plural)


def _present_obs(item: dict) -> str:
    if item["present"]:
        return f"present ({item['path']})"
    return "absent"


def _pytest_deductions(info: dict) -> dict:
    rule = f"{PYTEST_FAIL_POINTS} points each for failed and error, capped at {PYTEST_FAIL_CAP}; unusable JSON is {PYTEST_JSON_POINTS}"
    if info["status"] == "ok":
        points = min(PYTEST_FAIL_CAP, (info["failed"] + info["errors"]) * PYTEST_FAIL_POINTS)
        observation = f"{info['failed']} failed, {info['errors']} errors"
        return {
            "label": "pytest failures and errors",
            "points": points,
            "rule": rule,
            "observation": observation,
        }
    if info["status"] == "not_supplied":
        return {
            "label": "pytest failures and errors",
            "points": 0,
            "rule": rule,
            "observation": "not supplied; no deduction",
        }
    return {
        "label": "pytest JSON unusable",
        "points": PYTEST_JSON_POINTS,
        "rule": rule,
        "observation": info["status"],
    }


def _secrets_award(secrets: dict) -> int:
    if secrets["production_hits"]:
        return 0
    if secrets["non_production_hits"]:
        return max(0, _WEIGHT["secrets"] - FIXTURE_SECRET_POINTS)
    return _WEIGHT["secrets"]


def _secrets_observation(secrets: dict) -> str:
    if secrets["production_hits"]:
        return (
            f"{_count_phrase(secrets['production_hits'], 'production hit', 'production hits')} in "
            f"{_count_phrase(secrets['production_files'], 'file', 'files')}"
        )
    if secrets["non_production_hits"]:
        return (
            "0 production hits; "
            f"{_count_phrase(secrets['non_production_hits'], 'hit', 'hits')} in tests, fixtures, or docs in "
            f"{_count_phrase(secrets['non_production_files'], 'file', 'files')}"
        )
    return "none"


def _listed_paths(rows: list[dict], limit: int = 3) -> str:
    shown = [row["path"] for row in rows[:limit]]
    extra = len(rows) - len(shown)
    suffix = f" and {extra} more" if extra else ""
    return ", ".join(shown) + suffix


def _next_steps(data: dict) -> list[str]:
    steps: list[str] = []

    def add(text: str) -> None:
        if len(steps) < 5 and text not in steps:
            steps.append(text)

    secrets = data["secrets"]
    hygiene = data["hygiene"]
    deps = data["dependencies"]
    pytest_info = data["pytest"]
    ratio_total = deps["ratio_pinned"] + deps["ratio_unpinned"]
    if secrets["production_hits"]:
        add(
            "Remove "
            f"{_count_phrase(secrets['production_hits'], 'secrets-risk hit', 'secrets-risk hits')} "
            f"in production code ({_count_phrase(secrets['production_files'], 'file', 'files')}: "
            f"{_listed_paths(secrets['production_rows'])})."
        )
    if pytest_info["status"] == "ok" and (pytest_info["failed"] + pytest_info["errors"]) > 0:
        add(
            f"Fix {pytest_info['failed']} failed and {pytest_info['errors']} error pytest results, "
            "then pass a fresh pytest JSON file."
        )
    if data["test_files"] == 0:
        add(
            f"Add at least one test file. The scan counted {data['test_files']} test files and "
            f"{data['test_functions']} test functions."
        )
    elif data["test_functions"] == 0:
        add(
            f"Add test functions. {data['test_files']} test files contain {data['test_functions']} test functions."
        )
    if hygiene["large_binaries"]:
        top = hygiene["large_binaries"][0]
        add(
            f"Remove {len(hygiene['large_binaries'])} committed binaries or archives over {ONE_MB} bytes. "
            f"Largest: {top['path']} ({top['bytes']} bytes)."
        )
    if hygiene["large_json"]:
        top = hygiene["large_json"][0]
        add(
            f"Move {len(hygiene['large_json'])} JSON or JSONL files over {ONE_MB} bytes out of the checkout. "
            f"Largest: {top['path']} ({top['bytes']} bytes)."
        )
    if data["ci"]["configs"] == 0:
        add(f"Add a CI config. The scan found {data['ci']['configs']} configs and {data['ci']['jobs']} jobs.")
    elif data["ci"]["jobs"] == 0:
        add(f"Define at least one CI job. {data['ci']['configs']} configs declare {data['ci']['jobs']} jobs.")
    if deps["unpinned"] > 0:
        add(
            f"Pin {_count_phrase(deps['unpinned'], 'unpinned dependency', 'unpinned dependencies')} "
            f"({deps['ratio_pinned']} pinned of {ratio_total} parsed)."
        )
    elif deps["manifests"] == 0:
        add(f"Add a dependency manifest. The scan found {deps['manifests']} manifests.")
    if hygiene["scratch_dirs"]:
        shown = hygiene["scratch_dirs"][:3]
        extra = len(hygiene["scratch_dirs"]) - len(shown)
        suffix = f" and {extra} more" if extra else ""
        add(
            f"Remove {len(hygiene['scratch_dirs'])} scratch or attic directories: "
            f"{', '.join(shown)}{suffix}."
        )
    if hygiene["stray_tests"]:
        add(
            f"Move {len(hygiene['stray_tests'])} stray test files from the repo root or scripts into a tests directory: "
            f"{_listed_paths(hygiene['stray_tests'])}."
        )
    if secrets["non_production_hits"] and not secrets["production_hits"]:
        add(
            f"Review {secrets['non_production_hits']} secrets-risk hits in tests, fixtures, or docs "
            f"({_count_phrase(secrets['non_production_files'], 'file', 'files')}). Production hits: 0."
        )
    if not data["project_files"]["readme"]["present"]:
        add("Add a README at the checkout root. README count at root: 0.")
    if not data["project_files"]["gitignore"]["present"]:
        add("Add a .gitignore at the checkout root. .gitignore count at root: 0.")
    if data["markers"]["total"] >= MARKER_HYGIENE_FLOOR:
        top = data["markers"]["top_files"][0]
        add(
            f"Triage {data['markers']['total']} TODO, FIXME, and HACK markers, "
            f"starting with {top['path']} ({top['total']})."
        )
    if not data["project_files"]["license"]["present"]:
        add("Add a LICENSE file at the checkout root. LICENSE count at root: 0.")
    if pytest_info["status"] in {"malformed", "unexpected", "unreadable"}:
        add(f"Pass a readable pytest JSON file. Status: {pytest_info['status']}. Parsed counts: 0.")
    if pytest_info["status"] == "not_supplied":
        add("Pass a pytest JSON report with --pytest-json. Status: not supplied. Parsed counts: 0.")
    if data["scan_capped"]:
        add(f"The file cap was hit at {data['files']} files. Counts cover sorted walk order only.")
    if data["lines_partial_files"]:
        add(
            f"{data['lines_partial_files']} files exceeded the {data['limits']['max_file_read_bytes']} byte read cap, "
            "so their line counts cover the prefix only."
        )
    for filler in (
        (
            "Keep the measured test baseline: "
            f"{_count_phrase(data['test_files'], 'test file', 'test files')} and "
            f"{_count_phrase(data['test_functions'], 'test function', 'test functions')}."
        ),
        (
            "CI measurement: "
            f"{_count_phrase(data['ci']['configs'], 'config', 'configs')} and "
            f"{_count_phrase(data['ci']['jobs'], 'job', 'jobs')}."
        ),
        f"Dependency pin share: {deps['ratio_pinned']} pinned of {ratio_total} parsed, across {deps['manifests']} manifests.",
        (
            f"Secrets-risk measurement: {secrets['production_hits']} production hits and "
            f"{secrets['non_production_hits']} hits in tests, fixtures, or docs."
        ),
        (
            f"Repo-Hygiene measurement: {len(hygiene['large_binaries'])} binaries over {ONE_MB} bytes, "
            f"{len(hygiene['scratch_dirs'])} scratch directories, "
            f"{len(hygiene['large_json'])} JSON files over {ONE_MB} bytes, "
            f"{len(hygiene['stray_tests'])} stray test files."
        ),
    ):
        add(filler)
    return steps


def _pytest_lines(info: dict) -> list[str]:
    status = {
        "not_supplied": "not supplied",
        "ok": "parsed",
        "malformed": "could not be parsed",
        "unreadable": "could not be read",
        "unexpected": "unexpected shape",
    }[info["status"]]
    lines = [f"- Status: {status}"]
    if info["status"] == "ok":
        lines.extend(
            [
                f"- Passed: {info['passed']}",
                f"- Failed: {info['failed']}",
                f"- Skipped: {info['skipped']}",
                f"- Errors: {info['errors']}",
            ]
        )
    else:
        lines.extend(
            [
                "- Passed: n/a",
                "- Failed: n/a",
                "- Skipped: n/a",
                "- Errors: n/a",
            ]
        )
    return lines


def _limits() -> dict:
    return {
        "max_files": MAX_FILES,
        "max_file_read_bytes": MAX_FILE_READ_BYTES,
        "largest_limit": LARGEST_LIMIT,
        "marker_file_limit": MARKER_FILE_LIMIT,
        "skip_dirs": sorted(SKIP_DIR_NAMES),
    }


def _heading(german: str, english: str) -> list[str]:
    return _heading_level(2, german, english)


def _heading_level(level: int, german: str, english: str) -> list[str]:
    return [f"{'#' * level} {german}", f"_{english}_", ""]


def _render_summary(data: dict) -> list[str]:
    lines = _heading("Kurzfassung", "Executive summary")
    lines.extend(data["summary_sentences"])
    lines.append("")
    lines.extend(
        _table(
            ["Bereich", "Ampel", "Gemessen"],
            [[row["area"], row["light"], row["measured"]] for row in data["ampel"]],
        )
    )
    lines.append("")
    return lines


def _render_secrets(secrets: dict) -> list[str]:
    lines = _heading("Hinweise auf Geheimnisse", "Secrets-risk patterns")
    lines.append("Counts and file paths only. Matched text is not included.")
    lines.append("")
    lines.append(
        f"- Production hits: {secrets['production_hits']} in "
        f"{_count_phrase(secrets['production_files'], 'file', 'files')}"
    )
    lines.append(
        f"- Tests, fixtures, and docs hits: {secrets['non_production_hits']} in "
        f"{_count_phrase(secrets['non_production_files'], 'file', 'files')}"
    )
    lines.append(
        "- Production hits set the secrets-risk component to 0. "
        "Hits only in tests, fixtures, or docs cost 2 points."
    )
    lines.append("")
    lines.extend(_secret_bucket_table("Production code", secrets["production_rows"]))
    lines.append("")
    lines.extend(_secret_bucket_table("Tests, fixtures, and docs", secrets["non_production_rows"]))
    if secrets["pattern_rows"]:
        lines.append("")
        lines.extend(
            _table(
                ["Pattern", "Hits"],
                [[row["pattern"], row["hits"]] for row in secrets["pattern_rows"]],
            )
        )
    lines.append("")
    return lines


def _secret_bucket_table(title: str, rows: list[dict]) -> list[str]:
    lines = [f"### {title}", ""]
    shown, extra = _cap(rows, LIST_LIMIT)
    if shown:
        lines.extend(_table(["File", "Hits"], [[row["path"], row["hits"]] for row in shown]))
        if extra:
            lines.append(f"Showing {len(shown)} of {len(rows)} files.")
    else:
        lines.append("No secrets-risk patterns.")
    return lines


def _render_hygiene(data: dict) -> list[str]:
    hygiene = data["hygiene"]
    license_item = data["project_files"]["license"]
    lines = _heading("Repo-Hygiene", "Repository hygiene")
    if license_item["present"]:
        lines.append(f"- LICENSE: present ({license_item['path']})")
    else:
        lines.append("- LICENSE: absent")
    lines.append(f"- Binaries and archives over {ONE_MB} bytes: {len(hygiene['large_binaries'])}")
    lines.append(f"- Scratch or attic directories: {len(hygiene['scratch_dirs'])}")
    lines.append(f"- JSON or JSONL over {ONE_MB} bytes: {len(hygiene['large_json'])}")
    lines.append(f"- Stray test files: {len(hygiene['stray_tests'])}")
    lines.append("")
    if hygiene["large_binaries"]:
        shown, extra = _cap(hygiene["large_binaries"], LIST_LIMIT)
        lines.extend(_table(["Bytes", "File"], [[row["bytes"], row["path"]] for row in shown]))
        if extra:
            lines.append(f"Showing {len(shown)} of {len(hygiene['large_binaries'])} files.")
        lines.append("")
    if hygiene["scratch_dirs"]:
        shown, extra = _cap(hygiene["scratch_dirs"], LIST_LIMIT)
        lines.extend(_table(["Directory"], [[path] for path in shown]))
        if extra:
            lines.append(f"Showing {len(shown)} of {len(hygiene['scratch_dirs'])} directories.")
        lines.append("")
    if hygiene["large_json"]:
        shown, extra = _cap(hygiene["large_json"], LIST_LIMIT)
        lines.extend(_table(["Bytes", "File"], [[row["bytes"], row["path"]] for row in shown]))
        if extra:
            lines.append(f"Showing {len(shown)} of {len(hygiene['large_json'])} files.")
        lines.append("")
    if hygiene["stray_tests"]:
        shown, extra = _cap(hygiene["stray_tests"], LIST_LIMIT)
        lines.extend(
            _table(
                ["File", "Test functions"],
                [[row["path"], row["functions"]] for row in shown],
            )
        )
        if extra:
            lines.append(f"Showing {len(shown)} of {len(hygiene['stray_tests'])} files.")
        lines.append("")
    if not any(
        (
            hygiene["large_binaries"],
            hygiene["scratch_dirs"],
            hygiene["large_json"],
            hygiene["stray_tests"],
        )
    ):
        lines.append("No large binaries, scratch directories, large JSON files, or stray tests.")
        lines.append("")
    return lines


def _hygiene_flags(data: dict) -> list[str]:
    flags: list[str] = []
    if not data["project_files"]["readme"]["present"]:
        flags.append("readme")
    if not data["project_files"]["license"]["present"]:
        flags.append("license")
    if not data["project_files"]["gitignore"]["present"]:
        flags.append("gitignore")
    if data["markers"]["total"] >= MARKER_HYGIENE_FLOOR:
        flags.append("markers")
    hygiene = data["hygiene"]
    if hygiene["large_binaries"]:
        flags.append("binaries")
    if hygiene["scratch_dirs"]:
        flags.append("scratch")
    if hygiene["large_json"]:
        flags.append("json")
    if hygiene["stray_tests"]:
        flags.append("stray")
    return flags


def _ampel(data: dict) -> list[dict]:
    return [
        {"area": "Tests", "light": _tests_light(data), "measured": _tests_measured(data)},
        {"area": "CI", "light": _ci_light(data), "measured": _ci_measured(data)},
        {
            "area": "Abhängigkeiten",
            "light": _deps_light(data),
            "measured": _deps_measured(data),
        },
        {
            "area": "Geheimnis-Risiko",
            "light": _secrets_light(data),
            "measured": _secrets_measured(data),
        },
        {
            "area": "Repo-Hygiene",
            "light": _hygiene_light(data),
            "measured": _hygiene_measured(data),
        },
    ]


def _tests_light(data: dict) -> str:
    if data["test_files"] == 0 or data["test_functions"] == 0:
        return "Rot"
    info = data["pytest"]
    if info["status"] == "ok" and info["failed"] == 0 and info["errors"] == 0:
        return "Grün"
    return "Gelb"


def _tests_measured(data: dict) -> str:
    base = (
        f"{_de(data['test_files'], 'Testdatei', 'Testdateien')}, "
        f"{_de(data['test_functions'], 'Testfunktion', 'Testfunktionen')}"
    )
    info = data["pytest"]
    if info["status"] == "ok":
        return f"{base}, Pytest {info['failed']} fehlgeschlagen, {info['errors']} Fehler"
    if info["status"] == "not_supplied":
        return f"{base}, Pytest nicht geliefert"
    return f"{base}, Pytest nicht verwendbar"


def _ci_light(data: dict) -> str:
    if data["ci"]["configs"] == 0:
        return "Rot"
    if data["ci"]["jobs"] == 0:
        return "Gelb"
    return "Grün"


def _ci_measured(data: dict) -> str:
    return (
        f"{_de(data['ci']['configs'], 'Konfiguration', 'Konfigurationen')}, "
        f"{_de(data['ci']['jobs'], 'Job', 'Jobs')}"
    )


def _deps_light(data: dict) -> str:
    deps = data["dependencies"]
    if deps["manifests"] == 0:
        return "Rot"
    ratio_total = deps["ratio_pinned"] + deps["ratio_unpinned"]
    if ratio_total > 0 and deps["ratio_unpinned"] == 0:
        return "Grün"
    return "Gelb"


def _deps_measured(data: dict) -> str:
    deps = data["dependencies"]
    ratio_total = deps["ratio_pinned"] + deps["ratio_unpinned"]
    return (
        f"{_de(deps['manifests'], 'Manifest', 'Manifeste')}, "
        f"{deps['ratio_unpinned']} ungepinnt von {ratio_total}"
    )


def _secrets_light(data: dict) -> str:
    secrets = data["secrets"]
    if secrets["production_hits"] > 0:
        return "Rot"
    if secrets["non_production_hits"] > 0:
        return "Gelb"
    return "Grün"


def _secrets_measured(data: dict) -> str:
    secrets = data["secrets"]
    return (
        f"{secrets['production_hits']} Produktions-Treffer, "
        f"{secrets['non_production_hits']} Treffer in Tests/Fixtures/Docs"
    )


def _hygiene_light(data: dict) -> str:
    flags = data["hygiene"]["flags"]
    if any(name in flags for name in ("binaries", "json", "scratch")) or len(flags) >= 3:
        return "Rot"
    if flags:
        return "Gelb"
    return "Grün"


def _hygiene_measured(data: dict) -> str:
    hygiene = data["hygiene"]
    license_gaps = 0 if data["project_files"]["license"]["present"] else 1
    return (
        f"{_de(len(hygiene['flags']), 'Auffälligkeit', 'Auffälligkeiten')}, "
        f"{license_gaps} fehlende LICENSE, "
        f"{_de(len(hygiene['large_binaries']), 'Binärdatei', 'Binärdateien')}, "
        f"{_de(len(hygiene['scratch_dirs']), 'scratch/attic-Verzeichnis', 'scratch/attic-Verzeichnisse')}, "
        f"{_de(len(hygiene['large_json']), 'JSON/JSONL-Datei', 'JSON/JSONL-Dateien')}, "
        f"{_de(len(hygiene['stray_tests']), 'verstreute Testdatei', 'verstreute Testdateien')}"
    )


def _summary_sentences(data: dict) -> list[str]:
    hygiene = data["hygiene"]
    deps = data["dependencies"]
    secrets = data["secrets"]
    ratio_total = deps["ratio_pinned"] + deps["ratio_unpinned"]
    license_gaps = 0 if data["project_files"]["license"]["present"] else 1
    info = data["pytest"]
    if info["status"] == "ok":
        pytest_clause = (
            f"Pytest-JSON {info['passed']} bestanden, {info['failed']} fehlgeschlagen, "
            f"{info['skipped']} übersprungen, {info['errors']} Fehler"
        )
    elif info["status"] == "not_supplied":
        pytest_clause = "Pytest-JSON nicht geliefert, 0 Zählwerte"
    else:
        pytest_clause = "Pytest-JSON nicht verwendbar, 0 Zählwerte"
    parsed_noun = "Eintrag" if ratio_total == 1 else "Einträgen"
    return [
        f"Der Checkout enthält {_de(data['files'], 'Datei', 'Dateien')} und {_de(data['lines'], 'Zeile', 'Zeilen')}.",
        (
            f"Statisch gezählt wurden {_de(data['test_files'], 'Testdatei', 'Testdateien')}, "
            f"{_de(data['test_functions'], 'Testfunktion', 'Testfunktionen')} und "
            f"{_de(len(data['test_helpers']), 'Test-Hilfsdatei', 'Test-Hilfsdateien')}; "
            f"{pytest_clause}."
        ),
        (
            f"CI: {_de(data['ci']['configs'], 'Konfiguration', 'Konfigurationen')} und "
            f"{_de(data['ci']['jobs'], 'Job', 'Jobs')}."
        ),
        (
            f"Abhängigkeiten: {_de(deps['manifests'], 'Manifest', 'Manifeste')}, "
            f"{deps['ratio_pinned']} von {ratio_total} geparsten {parsed_noun} mit exakter Version."
        ),
        (
            f"Geheimnis-Risiko: {secrets['production_hits']} Treffer in Produktionscode und "
            f"{secrets['non_production_hits']} Treffer in Tests, Fixtures oder Docs."
        ),
        (
            f"Repo-Hygiene: {license_gaps} fehlende LICENSE, "
            f"{_de(len(hygiene['large_binaries']), 'Binär- oder Archivdatei', 'Binär- oder Archivdateien')} "
            f"über {ONE_MB} Bytes, "
            f"{_de(len(hygiene['scratch_dirs']), 'scratch/attic-Verzeichnis', 'scratch/attic-Verzeichnisse')}, "
            f"{_de(len(hygiene['large_json']), 'JSON/JSONL-Datei', 'JSON/JSONL-Dateien')} über {ONE_MB} Bytes, "
            f"{_de(len(hygiene['stray_tests']), 'verstreute Testdatei', 'verstreute Testdateien')}."
        ),
    ]


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(headers: list[str], rows: list[list[object]]) -> list[str]:
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(_cell(cell) for cell in row) + " |" for row in rows]
    return [head, sep, *body]


def _cap(rows: list, limit: int) -> tuple[list, int]:
    if len(rows) <= limit:
        return rows, 0
    return rows[:limit], len(rows) - limit


if __name__ == "__main__":
    sys.exit(main())
