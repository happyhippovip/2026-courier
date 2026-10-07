"""Linux-runnable contract for the Windows embeddable package.

The C# launcher starts ``courier_core``, ``courier_worker`` and ``courier_hub``
with the Python that ``scripts/windows_worker/build_package.ps1`` embeds.
That interpreter must satisfy ``pyproject.toml`` ``requires-python``, its
``pythonXY._pth`` must be the file that interpreter actually reads, and the
directories the script stages must be the packages setuptools would install
from ``[tool.setuptools.packages.find]``.

This test only reads source. It does not download Python, compile the
launcher, or touch the committed ``scripts/windows_worker/dist`` tree.
"""

from __future__ import annotations

import fnmatch
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts" / "windows_worker" / "build_package.ps1"
SMOKE_SCRIPT = ROOT / "scripts" / "windows_worker" / "smoke_package.ps1"
LAUNCHER = ROOT / "scripts" / "windows_worker" / "launcher" / "CourierLauncher.cs"
PYPROJECT = ROOT / "pyproject.toml"

# CPython SPDX package checksum for python-3.12.10-embed-amd64.zip.
EMBED_SHA256 = "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"

_VERSION_ASSIGNED = re.compile(r'\$PythonVersion\s*=\s*"(\d+\.\d+\.\d+)"')
_VERSION_URL = re.compile(r"python-(\d+\.\d+\.\d+)-embed-amd64\.zip")
_URL_FROM_VARIABLE = re.compile(r"python-\$PythonVersion-embed-amd64\.zip")
_PTH_NAME = re.compile(r"python\d+\._pth")
_RUNTIME_ARRAY = re.compile(r"^\$RuntimePackages\s*=\s*@\((.*?)\)", re.M | re.S)
_RUNTIME_LOOP = re.compile(r"foreach\s*\(\s*\$pkg\s+in\s+\$RuntimePackages\s*\)")
_COPY_PKG = re.compile(r"Copy-Item\b[^\n]*\$pkg")
_LEGACY_COPY = re.compile(
    r'Copy-Item\b[^\n]*-Destination\s+"\$OutDir\\([A-Za-z_][A-Za-z0-9_]*)"'
)
_LAUNCHER_MODULE = re.compile(
    r"-m\s+([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
)
_LAUNCHER_PYTHON_TAG = re.compile(r"python(\d{3})\b")
_EMBEDDED_EXE = re.compile(r'\$pythonExe\s*=\s*Join-Path\s+\$pyDir\s+"python\.exe"')
_UV_INSTALL = re.compile(r"uv\s+pip\s+install\b[^\n]*")


def _pyproject():
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _requires_python() -> str:
    spec = _pyproject()["project"]["requires-python"]
    if not isinstance(spec, str) or not spec.strip():
        raise AssertionError("pyproject.toml project.requires-python is missing")
    return spec.strip()


def _parse_version(version: str) -> tuple[int, ...]:
    parts = version.split(".")
    if not parts or any(not part.isdigit() for part in parts):
        raise AssertionError(f"not a numeric version: {version}")
    return tuple(int(part) for part in parts)


def _compare(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    width = max(len(left), len(right))
    a = left + (0,) * (width - len(left))
    b = right + (0,) * (width - len(right))
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def _satisfies(version: str, specifier: str) -> bool:
    """Enough of PEP 440 for the project's comma-separated requires-python."""
    current = _parse_version(version)
    clauses = [clause.strip() for clause in specifier.split(",") if clause.strip()]
    if not clauses:
        raise AssertionError(f"empty requires-python specifier: {specifier!r}")
    for clause in clauses:
        for op in (">=", "<=", "!=", "==", ">", "<"):
            if clause.startswith(op):
                other = _parse_version(clause[len(op) :].strip())
                cmp = _compare(current, other)
                ok = {
                    ">=": cmp >= 0,
                    "<=": cmp <= 0,
                    ">": cmp > 0,
                    "<": cmp < 0,
                    "==": cmp == 0,
                    "!=": cmp != 0,
                }[op]
                if not ok:
                    return False
                break
        else:
            raise AssertionError(f"unsupported requires-python clause: {clause}")
    return True


def embedded_python_version(text: str) -> str:
    assigned = _VERSION_ASSIGNED.findall(text)
    literals = _VERSION_URL.findall(text)
    versions = set(assigned) | set(literals)
    if len(versions) != 1:
        found = ", ".join(sorted(versions)) or "none"
        raise AssertionError(
            f"build_package.ps1 must pin exactly one embeddable Python, found {found}"
        )
    if not literals and not _URL_FROM_VARIABLE.search(text):
        raise AssertionError(
            "embeddable download URL is not derived from $PythonVersion"
        )
    return versions.pop()


def expected_pth_name(version: str) -> str:
    major, minor, *_rest = _parse_version(version)
    return f"python{major}{minor}._pth"


def declared_packages() -> set[str]:
    """Top-level packages setuptools include-globs select in this checkout.

    Globs that match nothing (a package that is named but not on disk yet)
    contribute no directory. A new directory that matches a glob must be
    staged, because ``uv pip install`` of the project root would install it.
    """
    includes = _pyproject()["tool"]["setuptools"]["packages"]["find"]["include"]
    if not isinstance(includes, list) or not includes:
        raise AssertionError("pyproject package include list is missing")
    found: set[str] = set()
    for child in ROOT.iterdir():
        if not child.is_dir() or not (child / "__init__.py").is_file():
            continue
        if any(fnmatch.fnmatchcase(child.name, pattern) for pattern in includes):
            found.add(child.name)
    if not found:
        raise AssertionError("no installable packages matched pyproject include globs")
    return found


def staged_packages(text: str) -> set[str]:
    array = _RUNTIME_ARRAY.search(text)
    if array and _RUNTIME_LOOP.search(text):
        if not _COPY_PKG.search(text):
            raise AssertionError(
                "RuntimePackages is declared but the loop does not Copy-Item $pkg"
            )
        names = re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"', array.group(1))
        if not names:
            raise AssertionError("RuntimePackages is empty")
        return set(names)
    return set(_LEGACY_COPY.findall(text))


def launcher_packages(text: str) -> set[str]:
    modules = _LAUNCHER_MODULE.findall(text)
    if not modules:
        raise AssertionError("CourierLauncher.cs does not start any python -m module")
    return {module.split(".", 1)[0] for module in modules}


def test_embedded_python_satisfies_requires_python():
    version = embedded_python_version(BUILD_SCRIPT.read_text(encoding="utf-8"))
    specifier = _requires_python()
    assert _satisfies(version, specifier), (
        f"build_package.ps1 embeds Python {version}, which does not satisfy "
        f"requires-python {specifier}"
    )


def test_pth_file_matches_embedded_python():
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    version = embedded_python_version(text)
    expected = expected_pth_name(version)
    found = set(_PTH_NAME.findall(text))
    assert found == {expected}, (
        f"build_package.ps1 patches {sorted(found) or 'no ._pth'}, "
        f"but Python {version} reads {expected}"
    )
    tags = set(_LAUNCHER_PYTHON_TAG.findall(LAUNCHER.read_text(encoding="utf-8")))
    expected_tag = expected.removesuffix("._pth")
    assert tags <= {expected_tag.removeprefix("python")}, (
        f"CourierLauncher.cs hardcodes python tag(s) {sorted(tags)}; "
        f"the embedded interpreter is {expected_tag}"
    )


def test_staged_packages_match_pyproject_and_launcher():
    build = BUILD_SCRIPT.read_text(encoding="utf-8")
    launcher = LAUNCHER.read_text(encoding="utf-8")
    staged = staged_packages(build)
    declared = declared_packages()
    launched = launcher_packages(launcher)
    assert staged == declared, (
        f"build_package.ps1 stages {sorted(staged) or 'nothing'}; "
        f"pyproject installs {sorted(declared)}; "
        f"missing {sorted(declared - staged)}; extra {sorted(staged - declared)}"
    )
    assert launched <= staged, (
        f"launcher starts {sorted(launched)} but the package does not stage "
        f"{sorted(launched - staged)}"
    )


def test_libs_install_targets_embedded_python():
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert _EMBEDDED_EXE.search(text), (
        "build_package.ps1 must install dependencies with the extracted "
        'python.exe (Join-Path $pyDir "python.exe")'
    )
    install = _UV_INSTALL.search(text)
    assert install, "build_package.ps1 does not run uv pip install"
    command = install.group(0)
    assert "--python" in command and "$pythonExe" in command, (
        "uv pip install must use --python $pythonExe so wheels match the "
        f"embedded interpreter; found: {command}"
    )
    assert "--target" in command and "libs" in command, (
        f"uv pip install must target the package libs directory; found: {command}"
    )
    after = text[install.end() :]
    assert re.search(r"\$LASTEXITCODE\s*-ne\s*0", after), (
        "uv pip install failure must abort the package build"
    )


def test_embed_zip_sha256_is_checked_before_extract():
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    match = re.search(r'\$PythonSha256\s*=\s*"([0-9A-Fa-f]{64})"', text)
    assert match, "build_package.ps1 must pin PythonSha256 for the embed zip"
    assert match.group(1).lower() == EMBED_SHA256
    filehash_at = text.find("Get-FileHash")
    expand_at = text.find("Expand-Archive")
    assert 0 <= match.start() < filehash_at < expand_at, (
        "SHA256 check must run after the pin is declared and before Expand-Archive"
    )
    assert "SHA256" in text[filehash_at:expand_at]


def test_smoke_checks_the_same_package_set_without_system_python():
    smoke = SMOKE_SCRIPT.read_text(encoding="utf-8")
    declared = set(re.findall(
        r'"([A-Za-z_][A-Za-z0-9_]*)"',
        re.search(r"^\$RequiredPackages\s*=\s*@\((.*?)\)", smoke, re.M | re.S).group(1),
    ))
    assert declared == staged_packages(BUILD_SCRIPT.read_text(encoding="utf-8"))
    assert "PYTHONPATH" in smoke and "PYTHONHOME" in smoke
    assert "Courier.exe" in smoke
    assert "python312._pth" in smoke
    assert "taskkill.exe /F /T /PID" in smoke
    assert "/IM" not in smoke
