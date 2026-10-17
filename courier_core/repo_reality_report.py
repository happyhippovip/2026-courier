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
    ("readme", 10, "README-Datei im Wurzelverzeichnis"),
    ("license", 5, "LICENSE-Datei im Wurzelverzeichnis"),
    ("gitignore", 8, ".gitignore im Wurzelverzeichnis"),
    ("test_files", 12, "mindestens eine Testdatei"),
    ("test_functions", 8, "mindestens eine Testfunktion"),
    ("ci_config", 10, "mindestens eine CI-Konfiguration"),
    ("ci_jobs", 5, "mindestens ein CI-Job"),
    ("manifest", 8, "mindestens ein Abhängigkeits-Manifest"),
    ("pinning", 14, "Anteil der Abhängigkeiten mit exakter Version oder Lockfile"),
    ("markers", 10, "1 Punkt Abzug je 5 TODO-, FIXME- oder HACK-Marker, nicht unter 0"),
    ("secrets", 10, "Treffer im Produktionscode ergeben 0; Treffer nur in Tests, Fixtures, Beispielen oder Doku kosten 2"),
)

PYTEST_FAIL_POINTS = 3
PYTEST_FAIL_CAP = 15
PYTEST_JSON_POINTS = 5

COMPONENT_LABELS = {
    "readme": "README",
    "license": "LICENSE",
    "gitignore": ".gitignore",
    "test_files": "Testdateien",
    "test_functions": "Testfunktionen",
    "ci_config": "CI-Konfiguration",
    "ci_jobs": "CI-Jobs",
    "manifest": "Abhängigkeits-Manifest",
    "pinning": "Gepinnte Abhängigkeiten",
    "markers": "Marker-Hygiene",
    "secrets": "Geheimnis-Hygiene",
}

_PY_TEST_NAME = re.compile(r"^(?:test_.+\.py|.+_test\.py)$", re.IGNORECASE)
_JS_TEST_NAME = re.compile(r"^.+\.(?:test|spec)\.(?:js|jsx|ts|tsx|mjs|cjs)$", re.IGNORECASE)
_GO_TEST_NAME = re.compile(r"^.+_test\.go$", re.IGNORECASE)
_TEST_DIR_NAMES = frozenset({"test", "tests", "__tests__"})
_PY_FUNC = re.compile(r"(?m)^[ \t]*(?:async[ \t]+def|def)[ \t]+test_[A-Za-z0-9_]*")
_JS_FUNC = re.compile(r"(?m)^[ \t]*(?:it|test)(?:\.(?:only|skip|each|concurrent|todo))?[ \t]*\(")
_GO_FUNC = re.compile(r"(?m)^func[ \t]+Test[A-Za-z0-9_]*[ \t]*\(")
# Rust: #[test], #[tokio::test] and similar attribute paths ending in ``test``.
_RS_FUNC = re.compile(r"(?m)^[ \t]*#\[(?:[A-Za-z_][A-Za-z0-9_]*::)*test\]")
_RS_CFG_TEST = re.compile(r"#\[cfg\(test\)\]")
_JS_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")
# A GitHub Actions expression such as ${{ secrets.NAME }} is a reference, not a value.
_GHA_EXPRESSION = "${{"
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
        "example",
        "examples",
        "fixture",
        "fixtures",
        "test",
        "testdata",
        "tests",
    }
)
_FIXTURE_DIRS = frozenset({"__fixtures__", "fixture", "fixtures", "testdata"})
# Lockfile name -> manifest kinds it pins when it sits in the manifest's folder or above.
_LOCK_COVERS = {
    "cargo.lock": ("cargo",),
    "composer.lock": ("composer",),
    "gemfile.lock": ("gemfile",),
    "go.sum": ("go.mod",),
    "package-lock.json": ("package.json",),
    "pipfile.lock": ("pipfile",),
    "pnpm-lock.yaml": ("package.json",),
    "poetry.lock": ("pyproject",),
    "uv.lock": ("pyproject",),
    "yarn.lock": ("package.json",),
}
_NOTE_LOCKFILE = "Lockfile"
_NOTE_UNPARSED = "nicht lesbar"
_NOTE_PREFIX = "nur Anfang gelesen"
_UNSUPPORTED_TEST_LANGUAGES = frozenset({"C", "C#", "C++", "Java", "Kotlin", "PHP", "Ruby", "Swift"})
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
        if is_test_file(rel, funcs, text):
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
                note = (note + "; " if note else "") + _NOTE_PREFIX
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

    _apply_lockfiles(manifest_rows)
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
    locked_manifests = sum(1 for row in manifest_rows if row.get("locked_by"))
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
            "locked_manifests": locked_manifests,
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
    """Render ``analyze`` output in German. The text contains counts and paths only."""
    lines: list[str] = ["# Repo Reality Check", ""]
    if evidence:
        lines.append(
            "Nur lesende Prüfung eines öffentlichen GitHub-Tarballs. Der Code des Repos wurde nicht ausgeführt. "
            "Testergebnisse erscheinen nur, wenn eine Pytest-JSON-Datei mitgeliefert wurde."
        )
        lines.append("")
        lines.append(f"- Quelle: {evidence['source']}")
        lines.append(f"- Commit: {evidence['sha']}")
        lines.append(f"- Tarball-Prüfsumme (sha256): {evidence['tarball_sha256']}")
        lines.append("")
    else:
        lines.append(
            "Nur lesende Prüfung eines lokalen Checkouts, ohne Netzwerkzugriff. Der Code des Repos wurde nicht ausgeführt. "
            "Testergebnisse erscheinen nur, wenn eine Pytest-JSON-Datei mitgeliefert wurde."
        )
        lines.append("")
    lines.extend(_render_summary(data))
    lines.extend(_heading("Repositorygröße", ""))
    lines.append(f"- Dateien: {data['files']}")
    lines.append(f"- Zeilen: {data['lines']}")
    if data["lines_partial_files"]:
        lines.append(
            f"- Nur teilweise gelesen (größer als {_kb(MAX_FILE_READ_BYTES)}): {data['lines_partial_files']}"
        )
    if data["scan_capped"]:
        lines.append(
            f"- Dateigrenze erreicht: gezählt wurden die ersten {data['files']} Dateien in sortierter Reihenfolge"
        )
    lines.append("")
    if data["languages"]:
        lines.extend(
            _table(
                ["Sprache", "Dateien", "Zeilen"],
                [[row["name"], row["files"], row["lines"]] for row in data["languages"]],
            )
        )
    else:
        lines.append("Keine Dateien.")
    lines.append("")

    lines.extend(_heading("Testdateien", ""))
    lines.append(f"- Testdateien: {data['test_files']}")
    lines.append(f"- Testfunktionen: {data['test_functions']}")
    lines.append(f"- Test-Hilfsdateien: {len(data['test_helpers'])}")
    lines.append("")
    shown, extra = _cap(data["test_file_rows"], LIST_LIMIT)
    if shown:
        lines.extend(_table(["Datei", "Testfunktionen"], [[row["path"], row["functions"]] for row in shown]))
        if extra:
            lines.append(f"Angezeigt: {len(shown)} von {data['test_files']} Testdateien.")
    else:
        lines.append("Keine Testdateien gefunden.")
    lines.append("")
    lines.extend(_heading_level(3, "Test-Hilfsdateien", ""))
    helpers, helper_extra = _cap(data["test_helpers"], LIST_LIMIT)
    if helpers:
        lines.extend(_table(["Datei"], [[path] for path in helpers]))
        if helper_extra:
            lines.append(f"Angezeigt: {len(helpers)} von {len(data['test_helpers'])} Test-Hilfsdateien.")
    else:
        lines.append("Keine Test-Hilfsdateien.")
    lines.append("")

    lines.extend(_heading("Testergebnisse", ""))
    lines.extend(_pytest_lines(data["pytest"]))
    lines.append("")

    markers = data["markers"]
    lines.extend(_heading("Offene Marker", ""))
    lines.append(f"- TODO: {markers['todo']}")
    lines.append(f"- FIXME: {markers['fixme']}")
    lines.append(f"- HACK: {markers['hack']}")
    lines.append(f"- Gesamt: {markers['total']}")
    lines.append("")
    if markers["top_files"]:
        lines.extend(
            _table(
                ["Datei", "TODO", "FIXME", "HACK", "Gesamt"],
                [
                    [row["path"], row["todo"], row["fixme"], row["hack"], row["total"]]
                    for row in markers["top_files"]
                ],
            )
        )
    else:
        lines.append("Keine Marker.")
    lines.append("")

    ci = data["ci"]
    lines.extend(_heading("CI-Konfiguration", ""))
    lines.append(f"- Konfigurationen: {ci['configs']}")
    lines.append(f"- Jobs: {ci['jobs']}")
    lines.append("")
    if ci["rows"]:
        lines.extend(
            _table(
                ["Art", "Datei", "Jobs"],
                [[row["kind"], row["path"], row["jobs"]] for row in ci["rows"]],
            )
        )
    else:
        lines.append("Keine CI-Konfiguration gefunden.")
    lines.append("")

    lines.extend(_heading("Projektdateien", ""))
    for key, label in (("readme", "README"), ("license", "LICENSE"), ("gitignore", ".gitignore")):
        lines.append(f"- {label}: {_present_obs(data['project_files'][key])}")
    lines.append("")

    deps = data["dependencies"]
    lines.extend(_heading("Abhängigkeiten", ""))
    lines.append(f"- Manifeste: {deps['manifests']}")
    lines.append(f"- Ohne exakte Version und ohne Lockfile: {deps['unpinned']}")
    lines.append(f"- Exakt gepinnt oder per Lockfile gesperrt: {deps['pinned']}")
    lines.append(
        "- Regel: requirements und PEP 621 gelten mit `==` oder `===` als gepinnt, package.json mit einer "
        "reinen Version major.minor.patch, Poetry, Cargo und Composer mit führendem `=`. Liegt ein passendes "
        "Lockfile (Cargo.lock, package-lock.json, yarn.lock, pnpm-lock.yaml, poetry.lock, uv.lock, Pipfile.lock, "
        "go.sum, Gemfile.lock, composer.lock) im selben oder einem übergeordneten Ordner, gelten alle Einträge "
        "des Manifests als gepinnt."
    )
    lines.append("")
    if deps["rows"]:
        lines.extend(
            _table(
                ["Manifest", "Art", "Gepinnt", "Ungepinnt", "Hinweis"],
                [
                    [row["path"], row["kind"], row["pinned"], row["unpinned"], row["note"] or "-"]
                    for row in deps["rows"]
                ],
            )
        )
    else:
        lines.append("Kein Abhängigkeits-Manifest gefunden.")
    lines.append("")

    lines.extend(_heading("Größte Dateien", ""))
    if data["largest"]:
        rows = []
        for row in data["largest"]:
            if row["binary"]:
                shown_lines = "binär"
            elif row["partial"]:
                shown_lines = f"{row['lines']} (Anfang)"
            else:
                shown_lines = row["lines"]
            rows.append([row["bytes"], shown_lines, row["path"]])
        lines.extend(_table(["Bytes", "Zeilen", "Datei"], rows))
    else:
        lines.append("Keine Dateien.")
    lines.append("")

    lines.extend(_render_secrets(data["secrets"]))
    lines.extend(_render_hygiene(data))

    score = data["score"]
    lines.extend(_heading("Realitätswert", ""))
    lines.append(f"Score: {score['value']} / 100")
    lines.append("")
    lines.append(
        f"Berechnung: {score['awarded']} Punkte vergeben, {score['deducted']} abgezogen = {score['raw']}, "
        f"auf 0 bis 100 begrenzt: {score['value']}."
    )
    lines.append("")
    lines.extend(
        _table(
            ["Komponente", "Gewicht", "Vergeben", "Regel", "Beobachtung"],
            [
                [row["label"], row["weight"], row["awarded"], row["rule"], row["observation"]]
                for row in score["components"]
            ],
        )
    )
    lines.append("")
    lines.extend(
        _table(
            ["Abzug", "Punkte", "Regel", "Beobachtung"],
            [
                [row["label"], row["points"], row["rule"], row["observation"]]
                for row in score["deductions"]
            ],
        )
    )
    lines.append("")

    lines.extend(_heading("Nächste fünf Schritte", ""))
    for index, step in enumerate(data["next_steps"], start=1):
        lines.append(f"{index}. {step}")
    lines.append("")

    limits = data["limits"]
    lines.extend(_heading("Grenzen", ""))
    lines.append(
        f"- Höchstens {limits['max_files']} Dateien; je Datei werden höchstens "
        f"{_kb(limits['max_file_read_bytes'])} gelesen."
    )
    lines.append("- Symbolische Links werden übersprungen.")
    lines.append("- Übersprungene Ordner: " + ", ".join(f"`{name}`" for name in limits["skip_dirs"]))
    lines.append(
        "- Als Testdatei gilt: test_*.py, *_test.py, *.test.* und *.spec.* (JS/TS) sowie *_test.go, wenn die Datei "
        "mindestens eine Testfunktion enthält oder in test/, tests/ oder __tests__/ liegt. Außerdem JS/TS-Dateien in "
        "diesen Ordnern mit mindestens einem it()- oder test()-Aufruf, Rust-Dateien mit #[test] oder #[cfg(test)] "
        "und Rust-Dateien in tests/. Fixture-Ordner zählen nicht."
    )
    lines.append(
        "- Testfunktionen werden per Textmuster gezählt (Python `def test_*`, JS/TS `it(`/`test(`, Go `func Test*`, "
        "Rust `#[test]`). Dateien werden nicht importiert. Rust-Tests aus eigenen Makros und Tests in anderen "
        "Sprachen (z. B. Java, Ruby, PHP) werden nicht erkannt."
    )
    lines.append(
        "- Test-Hilfsdateien sind conftest.py sowie fake/fakes- und builder/builders-Dateien in einem Testordner. "
        "Sie zählen nicht als Testdateien."
    )
    lines.append(
        "- Testdateien direkt im Wurzelverzeichnis oder in scripts/ sind ein Hygiene-Hinweis. Go-Testdateien "
        "neben dem Code sind üblich und zählen nicht dazu."
    )
    lines.append("- Marker sind die großgeschriebenen Wörter TODO, FIXME und HACK.")
    lines.append(
        "- Tests werden nicht ausgeführt. Bestanden, fehlgeschlagen und übersprungen stammen nur aus der "
        "optionalen Pytest-JSON-Datei."
    )
    lines.append(
        "- Geheimnis-Treffer in Tests, Fixtures, testdata/, Beispielen (examples/, example/), Doku oder Dateien "
        "wie README kosten 2 Punkte. Treffer im Produktionscode setzen die Komponente auf 0. GitHub-Actions-"
        "Ausdrücke wie `${{ secrets.NAME }}` zählen nicht. Der gefundene Text wird verworfen."
    )
    lines.append(
        "- Binär- und Archivdateien über 1 MB sowie JSON-, JSONL- und NDJSON-Dateien über 1 MB sind "
        "Hygiene-Hinweise."
    )
    lines.append("- Als scratch-Ordner gelten: attic, scratch, scratches, scratchpad.")
    lines.append(
        "- Ampel Tests: Rot bei 0 Testdateien oder 0 Testfunktionen; Grün, wenn beide vorhanden sind und das "
        "Pytest-Ergebnis 0 Fehlschläge und 0 Fehler zeigt; sonst Gelb."
    )
    lines.append(
        "- Ampel CI: Rot ohne Konfiguration; Gelb, wenn Konfigurationen keinen Job enthalten; Grün mit "
        "mindestens einem Job."
    )
    lines.append(
        "- Ampel Abhängigkeiten: Rot ohne Manifest; Grün, wenn jede erkannte Abhängigkeit gepinnt oder per "
        "Lockfile gesperrt ist; sonst Gelb."
    )
    lines.append(
        "- Ampel Geheimnis-Risiko: Rot bei Treffern im Produktionscode; Gelb bei Treffern nur in Tests, "
        "Fixtures, Beispielen oder Doku; Grün ohne Treffer."
    )
    lines.append(
        "- Ampel Repo-Hygiene: Rot bei großen Binär- oder JSON-Dateien, scratch/attic-Ordnern oder ab 3 "
        "Auffälligkeiten; Gelb bei 1 oder 2; Grün bei 0. Auffälligkeiten: fehlende README, LICENSE oder "
        ".gitignore, 5 oder mehr Marker, große Binärdateien, große JSON-Dateien, scratch/attic-Ordner, "
        "Testdateien außerhalb eines Testordners."
    )
    lines.append("- Der Wert ist die Summe der Gewichte oben. Er ist kein Sicherheitsurteil.")
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


def is_test_file(rel: str, function_count: int = 0, text: str = "") -> bool:
    """Decide whether ``rel`` is a test file.

    Test-named files (test_*.py, *_test.py, *.test.*, *.spec.*, *_test.go) count when they
    have a test function or live under a tests directory. JS/TS files inside test/, tests/
    or __tests__/ count when they call it() or test(). Rust files count when they contain
    #[test] or #[cfg(test)], or live under a tests directory.
    """
    name = rel.rsplit("/", 1)[-1]
    lower = name.lower()
    if _test_name_match(name):
        if function_count >= 1:
            return True
        return _under_test_dir(rel)
    in_test_dir = _under_test_dir(rel) and not _under_fixture_dir(rel)
    if lower.endswith(".rs"):
        return function_count >= 1 or bool(_RS_CFG_TEST.search(text)) or in_test_dir
    if lower.endswith(_JS_EXTS):
        return in_test_dir and function_count >= 1
    return False


def _test_name_match(name: str) -> bool:
    return bool(_PY_TEST_NAME.match(name) or _JS_TEST_NAME.match(name) or _GO_TEST_NAME.match(name))


def _under_test_dir(rel: str) -> bool:
    parents = [part.lower() for part in rel.split("/")[:-1]]
    return any(part in _TEST_DIR_NAMES for part in parents)


def _under_fixture_dir(rel: str) -> bool:
    parents = [part.lower() for part in rel.split("/")[:-1]]
    return any(part in _FIXTURE_DIRS for part in parents)


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
    if name.lower().endswith(".go"):
        # Go keeps *_test.go next to the code it tests. That is the convention, not clutter.
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
        return "ohne Endung", None
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
    if lower.endswith(_JS_EXTS):
        return len(_JS_FUNC.findall(text))
    if lower.endswith(".go"):
        return len(_GO_FUNC.findall(text))
    if lower.endswith(".rs"):
        return len(_RS_FUNC.findall(text))
    return 0


def _secret_hits(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name, pattern in _SECRET_PATTERNS:
        hits = sum(
            1
            for match in pattern.finditer(text)
            if not (name == "assigned_secret" and _GHA_EXPRESSION in match.group(0))
        )
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
    return _NOTE_UNPARSED not in note


def _apply_lockfiles(rows: list[dict]) -> None:
    """A manifest whose ecosystem lockfile sits in its folder or above counts as fully pinned."""
    locks: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        if row["kind"] != "lockfile":
            continue
        name = row["path"].rsplit("/", 1)[-1].lower()
        folder = row["path"].rsplit("/", 1)[0] if "/" in row["path"] else ""
        for kind in _LOCK_COVERS.get(name, ()):
            locks.setdefault(kind, []).append((folder, row["path"]))
    for row in rows:
        if row["kind"] == "lockfile" or not row["in_ratio"]:
            continue
        covering = [
            (folder, path)
            for folder, path in locks.get(row["kind"], ())
            if folder == "" or row["path"].startswith(folder + "/")
        ]
        if not covering:
            continue
        covering.sort(key=lambda item: (-len(item[0]), item[1]))
        lock_path = covering[0][1]
        row["pinned"] += row["unpinned"]
        row["unpinned"] = 0
        row["locked_by"] = lock_path
        note = f"gesperrt durch {lock_path}"
        row["note"] = f"{row['note']}; {note}" if row["note"] else note


def _count_dependencies(kind: str, text: str) -> tuple[int, int, str]:
    if kind == "lockfile":
        return 0, 0, _NOTE_LOCKFILE
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
        return 0, 0, _NOTE_UNPARSED
    if not isinstance(data, dict):
        return 0, 0, _NOTE_UNPARSED
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
        return 0, 0, _NOTE_UNPARSED
    if not isinstance(data, dict):
        return 0, 0, _NOTE_UNPARSED
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
        "test_files": _de(data["test_files"], "Datei", "Dateien"),
        "test_functions": _de(data["test_functions"], "Funktion", "Funktionen"),
        "ci_config": _de(data["ci"]["configs"], "Konfiguration", "Konfigurationen"),
        "ci_jobs": _de(data["ci"]["jobs"], "Job", "Jobs"),
        "manifest": _de(deps["manifests"], "Manifest", "Manifeste"),
        "markers": _de(data["markers"]["total"], "Marker", "Marker"),
        "secrets": _secrets_observation(secrets),
    }
    ratio_total = deps["ratio_pinned"] + deps["ratio_unpinned"]
    if ratio_total == 0 and deps.get("locked_manifests"):
        pin_awarded = _WEIGHT["pinning"]
        observations["pinning"] = "keine einzelnen Einträge, Lockfile vorhanden"
    elif ratio_total == 0:
        pin_awarded = 0
        observations["pinning"] = "keine erkannten Abhängigkeiten"
    else:
        pin_awarded = (_WEIGHT["pinning"] * deps["ratio_pinned"]) // ratio_total
        observations["pinning"] = f"{deps['ratio_pinned']} von {ratio_total} gepinnt"
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
        return f"vorhanden ({item['path']})"
    return "fehlt"


def _pytest_deductions(info: dict) -> dict:
    rule = (
        f"je {PYTEST_FAIL_POINTS} Punkte pro Fehlschlag oder Fehler, höchstens {PYTEST_FAIL_CAP}; "
        f"unbrauchbares JSON kostet {PYTEST_JSON_POINTS}"
    )
    if info["status"] == "ok":
        points = min(PYTEST_FAIL_CAP, (info["failed"] + info["errors"]) * PYTEST_FAIL_POINTS)
        observation = f"{info['failed']} fehlgeschlagen, {info['errors']} Fehler"
        return {
            "label": "Pytest: Fehlschläge und Fehler",
            "points": points,
            "rule": rule,
            "observation": observation,
        }
    if info["status"] == "not_supplied":
        return {
            "label": "Pytest: Fehlschläge und Fehler",
            "points": 0,
            "rule": rule,
            "observation": "nicht mitgeliefert, kein Abzug",
        }
    return {
        "label": "Pytest-JSON unbrauchbar",
        "points": PYTEST_JSON_POINTS,
        "rule": rule,
        "observation": _PYTEST_STATUS_DE[info["status"]],
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
            f"{secrets['production_hits']} Treffer im Produktionscode in "
            f"{_de(secrets['production_files'], 'Datei', 'Dateien')}"
        )
    if secrets["non_production_hits"]:
        return (
            "0 im Produktionscode; "
            f"{secrets['non_production_hits']} in Tests, Fixtures, Beispielen oder Doku in "
            f"{_de(secrets['non_production_files'], 'Datei', 'Dateien')}"
        )
    return "keine"


def _listed_paths(rows: list[dict], limit: int = 3) -> str:
    shown = [row["path"] for row in rows[:limit]]
    extra = len(rows) - len(shown)
    suffix = f" und {extra} weitere" if extra else ""
    return ", ".join(shown) + suffix


def _next_steps(data: dict) -> list[str]:
    """Up to five German next steps, findings first. Advice depends on the languages found."""
    steps: list[str] = []

    def add(text: str) -> None:
        if len(steps) < 5 and text not in steps:
            steps.append(text)

    secrets = data["secrets"]
    hygiene = data["hygiene"]
    deps = data["dependencies"]
    pytest_info = data["pytest"]
    ratio_total = deps["ratio_pinned"] + deps["ratio_unpinned"]
    python_tests = any(row["path"].lower().endswith(".py") for row in data["test_file_rows"])
    unsupported = sorted(
        row["name"] for row in data["languages"] if row["name"] in _UNSUPPORTED_TEST_LANGUAGES
    )
    if secrets["production_hits"]:
        add(
            f"{secrets['production_hits']} mögliche Geheimnis-Treffer im Produktionscode prüfen und echte Werte "
            f"entfernen ({_de(secrets['production_files'], 'Datei', 'Dateien')}: "
            f"{_listed_paths(secrets['production_rows'])})."
        )
    if pytest_info["status"] == "ok" and (pytest_info["failed"] + pytest_info["errors"]) > 0:
        add(
            f"{pytest_info['failed']} fehlgeschlagene und {pytest_info['errors']} fehlerhafte Pytest-Ergebnisse "
            "beheben, danach eine neue Pytest-JSON-Datei mitgeben."
        )
    if data["test_files"] == 0:
        if unsupported:
            add(
                "Keine Testdateien erkannt. Erkannt werden Python, JavaScript/TypeScript, Go und Rust; Tests in "
                f"{', '.join(unsupported)} bitte von Hand prüfen oder ergänzen."
            )
        else:
            add("Mindestens eine Testdatei anlegen. Der Scan hat keine Testdatei gefunden.")
    elif data["test_functions"] == 0:
        add(
            f"Testfunktionen ergänzen: {_de(data['test_files'], 'Testdatei enthält', 'Testdateien enthalten')} "
            "keine erkannte Testfunktion."
        )
    if hygiene["large_binaries"]:
        top = hygiene["large_binaries"][0]
        add(
            f"{_de(len(hygiene['large_binaries']), 'committete Binär- oder Archivdatei', 'committete Binär- oder Archivdateien')} "
            f"über 1 MB aus dem Repo entfernen. Größte: {top['path']} ({_mb(top['bytes'])})."
        )
    if hygiene["large_json"]:
        top = hygiene["large_json"][0]
        add(
            f"{_de(len(hygiene['large_json']), 'JSON/JSONL-Datei', 'JSON/JSONL-Dateien')} über 1 MB aus dem Repo "
            f"auslagern. Größte: {top['path']} ({_mb(top['bytes'])})."
        )
    if data["ci"]["configs"] == 0:
        add("Eine CI-Konfiguration anlegen, damit Tests bei jedem Push laufen. Gefunden wurde keine.")
    elif data["ci"]["jobs"] == 0:
        add(
            f"Mindestens einen CI-Job definieren: {_de(data['ci']['configs'], 'Konfiguration', 'Konfigurationen')} "
            "ohne erkannten Job."
        )
    if deps["unpinned"] > 0:
        add(
            f"{_de(deps['unpinned'], 'Abhängigkeit hat', 'Abhängigkeiten haben')} weder eine exakte Version noch "
            f"ein Lockfile ({deps['ratio_pinned']} von {ratio_total} gepinnt). Für Anwendungen ein Lockfile "
            "committen oder exakt pinnen; bei Bibliotheken sind Versionsbereiche üblich."
        )
    elif deps["manifests"] == 0:
        add("Ein Abhängigkeits-Manifest anlegen (z. B. pyproject.toml, package.json, go.mod oder Cargo.toml).")
    if hygiene["scratch_dirs"]:
        shown = hygiene["scratch_dirs"][:3]
        extra = len(hygiene["scratch_dirs"]) - len(shown)
        suffix = f" und {extra} weitere" if extra else ""
        add(
            f"{_de(len(hygiene['scratch_dirs']), 'scratch/attic-Ordner', 'scratch/attic-Ordner')} entfernen: "
            f"{', '.join(shown)}{suffix}."
        )
    if hygiene["stray_tests"]:
        add(
            f"{_de(len(hygiene['stray_tests']), 'Testdatei', 'Testdateien')} aus dem Wurzelverzeichnis oder "
            f"scripts/ in einen Testordner verschieben: {_listed_paths(hygiene['stray_tests'])}."
        )
    if secrets["non_production_hits"] and not secrets["production_hits"]:
        add(
            f"{secrets['non_production_hits']} Geheimnis-Treffer in Tests, Fixtures, Beispielen oder Doku kurz "
            f"prüfen ({_de(secrets['non_production_files'], 'Datei', 'Dateien')}). Im Produktionscode wurde "
            "nichts gefunden."
        )
    if not data["project_files"]["readme"]["present"]:
        add("Eine README im Wurzelverzeichnis anlegen.")
    if not data["project_files"]["gitignore"]["present"]:
        add("Eine .gitignore im Wurzelverzeichnis anlegen.")
    if data["markers"]["total"] >= MARKER_HYGIENE_FLOOR:
        top = data["markers"]["top_files"][0]
        add(
            f"{data['markers']['total']} TODO-, FIXME- und HACK-Marker sichten, beginnend mit "
            f"{top['path']} ({top['total']})."
        )
    if not data["project_files"]["license"]["present"]:
        add("Eine LICENSE-Datei im Wurzelverzeichnis anlegen.")
    if pytest_info["status"] in {"malformed", "unexpected", "unreadable"}:
        add(f"Eine lesbare Pytest-JSON-Datei mitgeben (Status: {_PYTEST_STATUS_DE[pytest_info['status']]}).")
    if pytest_info["status"] == "not_supplied" and python_tests:
        add(
            "Pytest-Ergebnisse mitliefern (pytest-json-report, Option --pytest-json), dann zeigt der Report "
            "bestandene und fehlgeschlagene Tests."
        )
    if data["scan_capped"]:
        add(
            f"Die Dateigrenze wurde erreicht: Die Zahlen decken nur die ersten {data['files']} Dateien ab. "
            "Für ein vollständiges Bild den Umfang absprechen."
        )
    if data["test_files"] and data["test_functions"]:
        add(
            f"Testbasis halten: {_de(data['test_files'], 'Testdatei', 'Testdateien')} mit "
            f"{_de(data['test_functions'], 'Testfunktion', 'Testfunktionen')} bei jedem Push in der CI ausführen."
        )
    if data["ci"]["jobs"]:
        add(
            f"CI beibehalten: {_de(data['ci']['configs'], 'Konfiguration', 'Konfigurationen')} mit "
            f"{_de(data['ci']['jobs'], 'Job', 'Jobs')}."
        )
    if deps["manifests"] and deps["unpinned"] == 0 and (ratio_total or deps.get("locked_manifests")):
        add("Versionsstand halten: alle erkannten Abhängigkeiten sind exakt gepinnt oder per Lockfile gesperrt.")
    if not secrets["production_hits"]:
        add("Geheimnis-Prüfung vor jedem Release wiederholen; im Produktionscode gab es diesmal keinen Treffer.")
    add("Diesen Check nach größeren Änderungen für den neuen Commit wiederholen und die Werte vergleichen.")
    return steps


def _pytest_lines(info: dict) -> list[str]:
    lines = [f"- Status: {_PYTEST_STATUS_DE[info['status']]}"]
    if info["status"] == "ok":
        lines.extend(
            [
                f"- Bestanden: {info['passed']}",
                f"- Fehlgeschlagen: {info['failed']}",
                f"- Übersprungen: {info['skipped']}",
                f"- Fehler: {info['errors']}",
            ]
        )
    else:
        lines.append("- Bestanden, fehlgeschlagen, übersprungen, Fehler: keine Angabe")
    return lines


_PYTEST_STATUS_DE = {
    "not_supplied": "nicht mitgeliefert",
    "ok": "ausgewertet",
    "malformed": "kein gültiges JSON",
    "unreadable": "Datei nicht lesbar",
    "unexpected": "unerwartetes Format",
}


def _kb(size: int) -> str:
    return f"{size // 1024} KB"


def _mb(size: int) -> str:
    return f"{size / ONE_MB:.1f} MB".replace(".", ",")


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


def _heading_level(level: int, german: str, _english: str = "") -> list[str]:
    return [f"{'#' * level} {german}", ""]


def _render_summary(data: dict) -> list[str]:
    lines = _heading("Kurzfassung", "")
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
    lines = _heading("Hinweise auf Geheimnisse", "")
    lines.append("Nur Anzahl und Dateipfad. Der gefundene Text wird nicht übernommen.")
    lines.append("")
    lines.append(
        f"- Treffer im Produktionscode: {secrets['production_hits']} in "
        f"{_de(secrets['production_files'], 'Datei', 'Dateien')}"
    )
    lines.append(
        f"- Treffer in Tests, Fixtures, Beispielen und Doku: {secrets['non_production_hits']} in "
        f"{_de(secrets['non_production_files'], 'Datei', 'Dateien')}"
    )
    lines.append(
        "- Treffer im Produktionscode setzen die Geheimnis-Komponente auf 0. Treffer nur in Tests, Fixtures, "
        "Beispielen oder Doku kosten 2 Punkte und sind ein Hinweis zum Prüfen."
    )
    lines.append("")
    lines.extend(_secret_bucket_table("Produktionscode", secrets["production_rows"]))
    lines.append("")
    lines.extend(_secret_bucket_table("Tests, Fixtures, Beispiele und Doku", secrets["non_production_rows"]))
    if secrets["pattern_rows"]:
        lines.append("")
        lines.extend(
            _table(
                ["Muster", "Treffer"],
                [[row["pattern"], row["hits"]] for row in secrets["pattern_rows"]],
            )
        )
    lines.append("")
    return lines


def _secret_bucket_table(title: str, rows: list[dict]) -> list[str]:
    lines = [f"### {title}", ""]
    shown, extra = _cap(rows, LIST_LIMIT)
    if shown:
        lines.extend(_table(["Datei", "Treffer"], [[row["path"], row["hits"]] for row in shown]))
        if extra:
            lines.append(f"Angezeigt: {len(shown)} von {len(rows)} Dateien.")
    else:
        lines.append("Keine Treffer.")
    return lines


def _render_hygiene(data: dict) -> list[str]:
    hygiene = data["hygiene"]
    lines = _heading("Repo-Hygiene", "")
    lines.append(f"- LICENSE: {_present_obs(data['project_files']['license'])}")
    lines.append(f"- Binär- oder Archivdateien über 1 MB: {len(hygiene['large_binaries'])}")
    lines.append(f"- scratch/attic-Ordner: {len(hygiene['scratch_dirs'])}")
    lines.append(f"- JSON/JSONL-Dateien über 1 MB: {len(hygiene['large_json'])}")
    lines.append(f"- Testdateien außerhalb eines Testordners: {len(hygiene['stray_tests'])}")
    lines.append("")
    if hygiene["large_binaries"]:
        shown, extra = _cap(hygiene["large_binaries"], LIST_LIMIT)
        lines.extend(_table(["Bytes", "Datei"], [[row["bytes"], row["path"]] for row in shown]))
        if extra:
            lines.append(f"Angezeigt: {len(shown)} von {len(hygiene['large_binaries'])} Dateien.")
        lines.append("")
    if hygiene["scratch_dirs"]:
        shown, extra = _cap(hygiene["scratch_dirs"], LIST_LIMIT)
        lines.extend(_table(["Ordner"], [[path] for path in shown]))
        if extra:
            lines.append(f"Angezeigt: {len(shown)} von {len(hygiene['scratch_dirs'])} Ordnern.")
        lines.append("")
    if hygiene["large_json"]:
        shown, extra = _cap(hygiene["large_json"], LIST_LIMIT)
        lines.extend(_table(["Bytes", "Datei"], [[row["bytes"], row["path"]] for row in shown]))
        if extra:
            lines.append(f"Angezeigt: {len(shown)} von {len(hygiene['large_json'])} Dateien.")
        lines.append("")
    if hygiene["stray_tests"]:
        shown, extra = _cap(hygiene["stray_tests"], LIST_LIMIT)
        lines.extend(
            _table(
                ["Datei", "Testfunktionen"],
                [[row["path"], row["functions"]] for row in shown],
            )
        )
        if extra:
            lines.append(f"Angezeigt: {len(shown)} von {len(hygiene['stray_tests'])} Dateien.")
        lines.append("")
    if not any(
        (
            hygiene["large_binaries"],
            hygiene["scratch_dirs"],
            hygiene["large_json"],
            hygiene["stray_tests"],
        )
    ):
        lines.append(
            "Keine großen Binär- oder JSON-Dateien, keine scratch-Ordner und keine Testdateien außerhalb "
            "eines Testordners."
        )
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
        return f"{base}, nicht ausgeführt"
    return f"{base}, Pytest-Datei nicht verwendbar"


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
    if deps["ratio_unpinned"] == 0 and (ratio_total > 0 or deps.get("locked_manifests")):
        return "Grün"
    return "Gelb"


def _deps_measured(data: dict) -> str:
    deps = data["dependencies"]
    ratio_total = deps["ratio_pinned"] + deps["ratio_unpinned"]
    if ratio_total == 0:
        tail = "Lockfile vorhanden" if deps.get("locked_manifests") else "keine Einträge erkannt"
        return f"{_de(deps['manifests'], 'Manifest', 'Manifeste')}, {tail}"
    return (
        f"{_de(deps['manifests'], 'Manifest', 'Manifeste')}, "
        f"{deps['ratio_unpinned']} von {ratio_total} ohne exakte Version oder Lockfile"
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
        f"{secrets['production_hits']} im Produktionscode, "
        f"{secrets['non_production_hits']} in Tests/Fixtures/Beispielen/Doku"
    )


def _hygiene_light(data: dict) -> str:
    flags = data["hygiene"]["flags"]
    if any(name in flags for name in ("binaries", "json", "scratch")) or len(flags) >= 3:
        return "Rot"
    if flags:
        return "Gelb"
    return "Grün"


def _hygiene_measured(data: dict) -> str:
    flags = data["hygiene"]["flags"]
    if not flags:
        return "keine Auffälligkeiten"
    return f"{_de(len(flags), 'Auffälligkeit', 'Auffälligkeiten')}: " + ", ".join(_hygiene_findings(data))


def _hygiene_findings(data: dict) -> list[str]:
    hygiene = data["hygiene"]
    texts = {
        "readme": "README fehlt",
        "license": "LICENSE fehlt",
        "gitignore": ".gitignore fehlt",
        "markers": f"{data['markers']['total']} Marker",
        "binaries": _de(len(hygiene["large_binaries"]), "Binärdatei über 1 MB", "Binärdateien über 1 MB"),
        "scratch": _de(len(hygiene["scratch_dirs"]), "scratch/attic-Ordner", "scratch/attic-Ordner"),
        "json": _de(len(hygiene["large_json"]), "JSON/JSONL-Datei über 1 MB", "JSON/JSONL-Dateien über 1 MB"),
        "stray": _de(
            len(hygiene["stray_tests"]),
            "Testdatei außerhalb eines Testordners",
            "Testdateien außerhalb eines Testordners",
        ),
    }
    return [texts[name] for name in hygiene["flags"]]


def _summary_sentences(data: dict) -> list[str]:
    hygiene = data["hygiene"]
    deps = data["dependencies"]
    secrets = data["secrets"]
    ratio_total = deps["ratio_pinned"] + deps["ratio_unpinned"]
    info = data["pytest"]
    if info["status"] == "ok":
        pytest_clause = (
            f"Pytest-Ergebnis: {info['passed']} bestanden, {info['failed']} fehlgeschlagen, "
            f"{info['skipped']} übersprungen, {info['errors']} Fehler"
        )
    elif info["status"] == "not_supplied":
        pytest_clause = "die Tests wurden nicht ausgeführt"
    else:
        pytest_clause = "die mitgelieferte Pytest-Datei war nicht verwendbar"
    if ratio_total == 0:
        tail = "Lockfile vorhanden, keine einzelnen Einträge" if deps.get("locked_manifests") else "keine einzelnen Einträge erkannt"
        deps_sentence = f"Abhängigkeiten: {_de(deps['manifests'], 'Manifest', 'Manifeste')}, {tail}."
    else:
        noun = "Eintrag" if ratio_total == 1 else "Einträgen"
        deps_sentence = (
            f"Abhängigkeiten: {_de(deps['manifests'], 'Manifest', 'Manifeste')}, {deps['ratio_pinned']} von "
            f"{ratio_total} {noun} exakt gepinnt oder per Lockfile gesperrt."
        )
    license_text = "LICENSE vorhanden" if data["project_files"]["license"]["present"] else "LICENSE fehlt"
    findings = [
        text
        for text, count in (
            (_de(len(hygiene["large_binaries"]), "Binär- oder Archivdatei über 1 MB", "Binär- oder Archivdateien über 1 MB"), len(hygiene["large_binaries"])),
            (_de(len(hygiene["scratch_dirs"]), "scratch/attic-Ordner", "scratch/attic-Ordner"), len(hygiene["scratch_dirs"])),
            (_de(len(hygiene["large_json"]), "JSON/JSONL-Datei über 1 MB", "JSON/JSONL-Dateien über 1 MB"), len(hygiene["large_json"])),
            (
                _de(len(hygiene["stray_tests"]), "Testdatei außerhalb eines Testordners", "Testdateien außerhalb eines Testordners"),
                len(hygiene["stray_tests"]),
            ),
        )
        if count
    ]
    if findings:
        hygiene_sentence = f"Repo-Hygiene: {license_text}; {', '.join(findings)}."
    else:
        hygiene_sentence = f"Repo-Hygiene: {license_text}, keine weiteren Auffälligkeiten."
    return [
        f"Der Checkout enthält {_de(data['files'], 'Datei', 'Dateien')} und {_de(data['lines'], 'Zeile', 'Zeilen')}.",
        (
            f"Statisch gezählt: {_de(data['test_files'], 'Testdatei', 'Testdateien')}, "
            f"{_de(data['test_functions'], 'Testfunktion', 'Testfunktionen')} und "
            f"{_de(len(data['test_helpers']), 'Test-Hilfsdatei', 'Test-Hilfsdateien')}; "
            f"{pytest_clause}."
        ),
        (
            f"CI: {_de(data['ci']['configs'], 'Konfiguration', 'Konfigurationen')} und "
            f"{_de(data['ci']['jobs'], 'Job', 'Jobs')}."
        ),
        deps_sentence,
        (
            f"Geheimnis-Risiko: {secrets['production_hits']} Treffer im Produktionscode, "
            f"{secrets['non_production_hits']} in Tests, Fixtures, Beispielen oder Doku."
        ),
        hygiene_sentence,
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
