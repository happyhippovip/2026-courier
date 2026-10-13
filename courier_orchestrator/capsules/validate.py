"""Automatic capsule checks: schema, license allowlist, secrets, forbidden imports, size."""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .schema import LICENSE_ALLOWLIST, MAX_CAPSULE_BYTES, REQUIRED_FIELDS, SCHEMA_VERSION, Capsule

SECRET_PATTERNS = {
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "openai_like_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "generic_secret": re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"),
}
# private project data markers (emails, absolute home paths)
PRIVATE_DATA_PATTERNS = {
    "email_address": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "home_path": re.compile(r"(/home/|/Users/|C:\\\\Users\\\\)[^\s'\"]+"),
}
FORBIDDEN_IMPORTS = frozenset({"os", "subprocess", "socket", "shutil", "ctypes", "importlib", "pickle",
                               "marshal", "requests", "urllib", "http", "ftplib", "telnetlib", "multiprocessing"})
FORBIDDEN_CALLS = frozenset({"eval", "exec", "compile", "__import__", "open"})


@dataclass
class ValidationResult:
    ok: bool
    errors: List[str] = field(default_factory=list)


def _strings(obj: Any):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _strings(v)


def _check_code(name: str, src: str, errors: List[str]) -> None:
    try:
        tree = ast.parse(src, filename=name)
    except SyntaxError as e:
        errors.append(f"code:{name}: syntax error {e.msg}")
        return
    for node in ast.walk(tree):
        mods: List[str] = []
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [node.module or ""]
        for m in mods:
            if m.split(".")[0] in FORBIDDEN_IMPORTS:
                errors.append(f"code:{name}: forbidden import {m}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            errors.append(f"code:{name}: forbidden call {node.func.id}()")


def validate_capsule(data: Dict[str, Any] | Capsule) -> ValidationResult:
    if isinstance(data, Capsule):
        data = data.to_dict()
    errors: List[str] = []
    if not isinstance(data, dict):
        return ValidationResult(False, ["schema: capsule must be an object"])
    size = len(json.dumps(data, sort_keys=True).encode("utf-8"))
    if size > MAX_CAPSULE_BYTES:
        errors.append(f"size: {size} bytes > limit {MAX_CAPSULE_BYTES}")
    for f in REQUIRED_FIELDS:
        if f not in data or data[f] in (None, "", [], {}):
            errors.append(f"schema: missing field {f}")
    if data.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        errors.append("schema: unsupported schema_version")
    types = {"inputs": dict, "worker_requirements": dict, "cost_profile": dict, "output_schema": dict,
             "planning_pattern": list, "verification_pattern": list, "failure_modes": list}
    for f, t in types.items():
        if f in data and not isinstance(data[f], t):
            errors.append(f"schema: {f} must be {t.__name__}")
    if "capsule_id" in data and not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", str(data["capsule_id"])):
        errors.append("schema: invalid capsule_id")
    if data.get("license") not in LICENSE_ALLOWLIST:
        errors.append(f"license: {data.get('license')!r} not in allowlist")
    for s in _strings({k: v for k, v in data.items() if k != "author"}):
        for name, pat in SECRET_PATTERNS.items():
            if pat.search(s):
                errors.append(f"secret: {name} detected")
        for name, pat in PRIVATE_DATA_PATTERNS.items():
            if pat.search(s):
                errors.append(f"private_data: {name} detected")
    code = data.get("code") or {}
    if not isinstance(code, dict):
        errors.append("schema: code must be dict")
    else:
        for name, src in code.items():
            _check_code(name, str(src), errors)
    return ValidationResult(not errors, sorted(set(errors)))
