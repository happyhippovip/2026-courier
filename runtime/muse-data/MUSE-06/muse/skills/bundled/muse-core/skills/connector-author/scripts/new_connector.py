#!/usr/bin/env python3
"""connector-author scaffold (ADR 37480 D12; spec 25011 FR-37480-44).

    new_connector.py scaffold --connector <name> --delivery poll|push|stream \
        --answers <json file or -> [--plugin <id>] [--root <dir>]
    new_connector.py check --skill-dir <dir> [--tests-dir <dir>]

`scaffold` copies the starter template (`../templates/`) into a project skill
(`<root>/.agents/skills/<name>/`, the default) or a plugin package
(`<root>/crates/plugins/<id>/`, shaped like the general event-stream
connector's plugin) with the interview
answers filled in. The three mechanical rules come from the template; every
source-specific body is a stub whose `TODO(answer <id>)` marker names the
answer that fills it. The write is all-or-nothing: the tree is built in a
staging directory and moved into place only when every target path is free;
a refusal leaves nothing on disk (INV-37480-44). `--delivery stream` writes
nothing and prints the redirect to the connector that already carries the
source. `check` runs the shared `connector_conformance.py` and the generated
tests against a scaffolded (or filled-in) connector and prints one JSON line.
Stdlib only; one JSON line per verb on stdout, `outcome` first.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE.parent / "templates"
CONFORMANCE = HERE / "connector_conformance.py"
NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
DELIVERIES = ("poll", "push", "stream")
# The top-level groups of the answers object (FR-37480-44(b)); `handle` is the
# template's optional mention handle override.
ANSWER_GROUPS = ("source", "delivery", "poll", "push", "stream", "auth", "conversation", "reply",
                 "filters", "gate", "placement", "name", "connect_words", "handle")
ANSWER_IDS = (
    "source.name", "source.word", "source.summary", "delivery",
    "poll.command", "poll.output", "poll.interval_s", "push.port", "push.payload",
    "stream.connector", "stream.source", "auth.identity", "auth.env",
    "conversation.unit", "conversation.id_rule", "reply.command", "reply.summary", "reply.markdown",
    "filters.default", "filters.meaning", "gate.experimental_tag", "placement.kind", "placement.plugin_id",
    "name", "connect_words",
)


def emit(payload: dict, code: int = 0) -> None:
    print(json.dumps(payload), flush=True)
    sys.exit(code)


def refuse(reason: str, **extra) -> None:
    emit({"outcome": "refused", "reason": reason, **extra}, 2)


def get(answers: dict, dotted: str, default=None):
    node = answers
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def load_answers(spec: str) -> dict:
    try:
        raw = sys.stdin.read() if spec == "-" else Path(spec).read_text(encoding="utf-8")
        answers = json.loads(raw)
    except (OSError, ValueError) as exc:
        refuse("answers_unreadable", detail=str(exc))
    if not isinstance(answers, dict):
        refuse("answers_not_an_object")
    unknown = sorted(key for key in answers if key not in ANSWER_GROUPS)
    if unknown:
        # FR-37480-44(e): a key outside the fixed list is malformed; a MISSING
        # key is not — it leaves that stub TODO and is listed under `todo`.
        refuse("answers_unknown_key", unknown=unknown, known=sorted(ANSWER_GROUPS))
    return answers


# --- rendering -----------------------------------------------------------------

def render(template: str, fields: dict) -> str:
    out = template
    for key, value in fields.items():
        out = out.replace("{{" + key + "}}", str(value))
    left = re.findall(r"\{\{([A-Z_]+)\}\}", out)
    if left:
        raise KeyError(f"unfilled template fields: {sorted(set(left))}")
    return out


def fields_for(name: str, delivery: str, answers: dict) -> tuple[dict, list[str]]:
    todo: list[str] = []

    def answer(dotted: str, default=None, todo_note: str | None = None):
        value = get(answers, dotted)
        if value in (None, "", []):
            if todo_note:
                todo.append(f"- `{dotted}` — {todo_note}")
            return default
        return value

    source_name = answer("source.name", name, "what the source is (fills the SKILL's description)")
    source_word = answer("source.word", name[:-len("-connector")] if name.endswith("-connector") else name)
    if not NAME_RE.match(str(source_word)) and not re.match(r"^[a-z][a-z0-9._-]*$", str(source_word)):
        refuse("source_word_invalid", word=source_word)
    source_summary = answer("source.summary", "", "one sentence on where the messages appear")
    poll_command = answer("poll.command", None, "the command that lists new events (poll delivery)") if delivery == "poll" else None
    push_port = answer("push.port", None, "the local port the source posts to (push delivery)") if delivery == "push" else None
    reply_command = answer("reply.command", None, "the verb that posts a reply into one conversation")
    reply_summary = answer("reply.summary", reply_command or "the source's own reply verb")
    conversation_unit = answer("conversation.unit", "one conversation", "what one alias `c<n>` stands for")
    conversation_id_rule = answer("conversation.id_rule", "the id the source gives that container", "the stable id rule the registry keys on")
    auth_identity = answer("auth.identity", "The connector acts as the account the source's own login provides.", "which account the connector acts as")
    auth_env = answer("auth.env", [])
    if not isinstance(auth_env, list) or any(not isinstance(n, str) or not ENV_RE.match(n) for n in auth_env):
        refuse("auth_env_invalid", detail="auth.env must be a list of environment variable NAMES")
    default_filter = answer("filters.default", "mention")
    filter_meaning = answer("filters.meaning", "your handle appears in the text", "what \"addressed to me\" means on this source")
    gate = get(answers, "gate.experimental_tag", True)
    connect_words = answer("connect_words", [f"connect {source_word}"])
    if isinstance(connect_words, str):
        connect_words = [connect_words]
    if not isinstance(connect_words, list) or any(not isinstance(w, str) for w in connect_words):
        refuse("connect_words_invalid", detail="connect_words must be a list of strings")
    if push_port is not None and not (isinstance(push_port, int) or (isinstance(push_port, str) and push_port.isdigit())):
        refuse("push_port_invalid", detail="push.port must be an integer port number", port=push_port)
    interval = get(answers, "poll.interval_s")
    if interval is not None and not isinstance(interval, (int, float)):
        refuse("poll_interval_invalid", detail="poll.interval_s must be a number", interval=interval)
    markdown = get(answers, "reply.markdown")
    env_prefix = re.sub(r"[^A-Z0-9]", "_", name.upper()) + "_"
    module = re.sub(r"[^a-z0-9]", "_", name) + ".py"
    if delivery == "poll":
        delivery_sentence = (f"poll — `{poll_command}` is asked every {answer('poll.interval_s', 5)} s"
                             if poll_command else "poll — the command is not filled in yet (`poll.command`)")
    else:
        delivery_sentence = (f"push — the source POSTs JSON events to `http://127.0.0.1:{push_port}/`"
                             if push_port else "push — the local endpoint's port is not filled in yet (`push.port`)")
    fields = {
        "NAME": name,
        "SOURCE_NAME": source_name,
        "SOURCE_WORD": source_word,
        "SOURCE_SUMMARY": source_summary,
        "DELIVERY": delivery,
        "DELIVERY_SENTENCE": delivery_sentence,
        "CONVERSATION_UNIT": conversation_unit,
        "CONVERSATION_ID_RULE": conversation_id_rule,
        "AUTH_IDENTITY": auth_identity,
        "AUTH_ENV_LIST": ", ".join(f"`{n}`" for n in auth_env) if auth_env else "none",
        "AUTH_ENV_DOC": (", plus " + ", ".join(f"`{n}`" for n in auth_env) + " (answer auth.env)") if auth_env else "",
        "DEFAULT_FILTER": default_filter,
        "FILTER_MEANING": filter_meaning,
        "POLL_COMMAND": repr(poll_command),
        "PUSH_PORT": repr(int(push_port)) if push_port else repr(None),
        "REPLY_COMMAND": repr(reply_command),
        "REPLY_SUMMARY": reply_summary,
        "REPLY_SENTENCE": (f"`reply --to c<n>` runs `{reply_command}` with `{{conversation}}` and `{{text}}` filled in."
                           if reply_command else "`reply --to c<n>` is not wired to the source yet (`reply.command`)."),
        "MARKDOWN_NOTE": (" (markdown renders)" if markdown else (" (no markdown)" if markdown is False else "")),
        "ENV_PASS": repr(list(auth_env)),
        "ENV_PREFIX": env_prefix,
        "HANDLE": get(answers, "handle", "@muse"),
        "POLL_S": str(answer("poll.interval_s", 5)) if delivery == "poll" else "1",
        "SCRIPT_NAME": module,
        "GATE_LINE": "experimental-gate: tag\n" if gate else "",
        "CONNECT_WORDS": ", ".join(f'"{w}"' for w in connect_words),
        "DATE": _dt.date.today().isoformat(),
        "TODO_LIST": "\n".join(todo) if todo else "Nothing: every answer the template consumes was given.",
    }
    return fields, todo


# --- the plugin-package files (short; the shape of a bundled connector plugin crate) ---

def plugin_manifest(plugin_id: str, name: str, source_name: str) -> str:
    return json.dumps({
        "schemaVersion": 1,
        "name": plugin_id,
        "displayName": plugin_id.replace("-", " ").title(),
        "version": "0.1.0",
        "description": f"Daemon connector for {source_name}.",
        "compat": {"source": "native", "manifestDir": ".muse-plugin"},
        "capabilities": {
            "skills": [{"id": name, "path": f"skills/{name}/SKILL.md", "enabledDefault": True}],
            "developerPrompts": [], "hooks": [], "mcpServers": [], "commands": [], "reminders": [],
        },
    }, indent=2) + "\n"


def cargo_toml(plugin_id: str) -> str:
    return (f'[package]\nname = "tbh-{plugin_id}"\nversion = "0.1.0"\nedition.workspace = true\n'
            'license.workspace = true\npublish = false\n\n[dependencies]\ntbh-config.workspace = true\n'
            'tbh-plugins.workspace = true\n\n[dev-dependencies]\nserde_json = "1"\n\n[lints]\nworkspace = true\n')


def lib_rs(plugin_id: str, name: str, module: str) -> str:
    gate_id = re.sub(r"[^a-z0-9]", "_", plugin_id) + "_plugin"
    return f'''#![deny(clippy::print_stderr, clippy::print_stdout)]

//! Compiled descriptor for the `{name}` daemon connector plugin (scaffolded
//! by connector-author, ADR 37480 D9/D12): a `CompiledPlugin::bundled` package
//! carrying the skill body and its connector script behind a product gate.
//! Register it at the X1 roster marker in product composition before it ships.

use tbh_config::{{GateDefinition, GateKey, GateRegistryError}};
use tbh_plugins::{{BundledFile, BundledPlugin, CompiledPlugin}};

const PLUGIN_ID: &str = "{plugin_id}";
pub const GATE_ID: &str = "{gate_id}";

const SKILL_FILES: &[BundledFile] = &[
    BundledFile::text("skills/{name}/SKILL.md", include_str!("../skills/{name}/SKILL.md")),
    BundledFile::text(
        "skills/{name}/scripts/{module}",
        include_str!("../skills/{name}/scripts/{module}"),
    ),
];

pub fn plugin() -> Result<CompiledPlugin, GateRegistryError> {{
    Ok(CompiledPlugin::bundled(
        PLUGIN_ID,
        GateDefinition::product(GateKey::new(GATE_ID)?, true),
        BundledPlugin {{ manifest_json: include_str!("../plugin.json"), files: SKILL_FILES }},
    ))
}}
'''


def gate_posture_rs(plugin_id: str, name: str, gate: bool) -> str:
    crate = "tbh_" + re.sub(r"[^a-z0-9]", "_", plugin_id)
    tag_assert = ('    assert!(frontmatter.lines().any(|line| line == "experimental-gate: tag"));\n' if gate else "")
    return f'''//! The scaffolded plugin declares exactly its connector skill, binds one
//! product gate, and (when asked for) keeps the `tag` experimental gate in the
//! skill frontmatter (ADR 37480 D9 Amendment 1, D12).

const SKILL_MD: &str = include_str!("../skills/{name}/SKILL.md");
const MANIFEST: &str = include_str!("../plugin.json");

#[test]
fn manifest_declares_the_connector_skill_and_the_gate_binds() {{
    let manifest: serde_json::Value = serde_json::from_str(MANIFEST).expect("manifest parses");
    assert_eq!(manifest["name"], "{plugin_id}");
    assert_eq!(manifest["capabilities"]["skills"][0]["id"], "{name}");
    assert!(manifest.get("when").is_none(), "no pane predicate: the daemon runs in tmux");
    let frontmatter = SKILL_MD
        .strip_prefix("---\\n")
        .and_then(|rest| rest.split_once("\\n---\\n"))
        .map(|(front, _)| front)
        .expect("SKILL.md starts with frontmatter");
    assert!(frontmatter.lines().any(|line| line == "name: {name}"));
{tag_assert}    assert_eq!({crate}::GATE_ID, "{re.sub(r"[^a-z0-9]", "_", plugin_id)}_plugin");
    {crate}::plugin().expect("the plugin declares");
}}
'''


TEST_CONFORMANCE = '''"""Conformance of the `{name}` connector to the daemon's three mechanical
rules (ADR 37480 D1/D8), through the shared `connector_conformance.py` and a
fixture inbox — no real source is reached. Keep it green after filling the
stubs: the fixture branches are what it drives.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = {script_expr}
ANSWERS = json.loads((HERE / "answers.json").read_text())
SOURCE = ANSWERS.get("source", {{}}).get("word") or "{source_word}"
PREFIX = "{env_prefix}"


class Conformance(unittest.TestCase):
    def test_the_three_rules_hold(self):
        with tempfile.TemporaryDirectory(prefix="{name}-") as tmp:
            fixture = pathlib.Path(tmp) / "fixture.json"
            fixture.write_text(json.dumps({{"inbound": {{SOURCE: [
                {{"id": "e1", "sender": "alice", "text": "@muse hello", "conversation": SOURCE + ":1"}},
                {{"id": "e2", "sender": "bob: ops", "text": "@muse first line\\nsecond line", "conversation": SOURCE + ":2"}}]}}}}))
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            env[PREFIX + "FIXTURE_FILE"] = str(fixture)
            env[PREFIX + "STATE_DIR"] = str(pathlib.Path(tmp) / "state")
            env[PREFIX + "POLL_S"] = "0.05"
            result = subprocess.run(
                [sys.executable, "-B", str(HERE / "connector_conformance.py"), str(SCRIPT),
                 "--listen", "--source", SOURCE, "--reply-to", "c1"],
                capture_output=True, text=True, env=env, timeout=120, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for rule in ("single-listener refusal", "reply idempotency", "feed grammar"):
                self.assertIn(rule + ": ok", result.stdout)

    def test_status_declares_its_sources_cold_and_live(self):
        # The daemon's `start` reads `sources_available` and the per-source
        # `listeners` record; a status without them marks a live row stale.
        with tempfile.TemporaryDirectory(prefix="{name}-") as tmp:
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            env[PREFIX + "FIXTURE_FILE"] = str(pathlib.Path(tmp) / "fixture.json")
            env[PREFIX + "STATE_DIR"] = str(pathlib.Path(tmp) / "state")
            env[PREFIX + "POLL_S"] = "0.05"

            def status():
                proc = subprocess.run([sys.executable, "-B", str(SCRIPT), "status", "--json"],
                                      capture_output=True, text=True, env=env, timeout=60, check=False)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                return json.loads(proc.stdout.strip().splitlines()[-1])

            cold = status()
            self.assertIn(SOURCE, cold["sources_available"])
            self.assertEqual(cold["listeners"][SOURCE]["listener"], "absent")
            listener = subprocess.Popen([sys.executable, "-B", str(SCRIPT), "listen", "--source", SOURCE, "--filter", "mention"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, env=env)
            try:
                self.assertIn("listening", listener.stderr.readline())  # live: its first stderr line
                live = status()
                self.assertEqual(live["listeners"][SOURCE],
                                 {{"listener": "live", "pid": listener.pid, "subscriptions": [SOURCE + "|mention"]}})
                self.assertEqual(live["listeners"][SOURCE + "|mention"], {{"listener": "live", "pid": listener.pid}})
                # A listener that ends non-zero leaves `exit` and `ended_at` on its
                # records (the daemon's `start` records the failure from them);
                # here the fixture it polls stops being JSON.
                pathlib.Path(env[PREFIX + "FIXTURE_FILE"]).write_text("{{not json")
                self.assertEqual(listener.wait(timeout=60), 1)
                ended = status()["listeners"]
                self.assertEqual(ended[SOURCE + "|mention"]["exit"], 1, ended)
                self.assertEqual(ended[SOURCE]["exit"], 1, ended)
                self.assertRegex(ended[SOURCE]["ended_at"], r"^\\d{{4}}-\\d{{2}}-\\d{{2}}T\\d{{2}}:\\d{{2}}:\\d{{2}}Z$")
                # The record lands whole (tmp + rename): nothing else is left beside it.
                self.assertEqual([p.name for p in (pathlib.Path(env[PREFIX + "STATE_DIR"]) / "listeners").iterdir()],
                                 [SOURCE + "--mention.ended"])
            finally:
                listener.terminate()
                listener.communicate(timeout=60)


if __name__ == "__main__":
    unittest.main()
'''

RUN_SH = '''#!/usr/bin/env bash
# Offline contract suite for the {name} connector (stdlib unittest; the
# fixture inbox stands in for the source).
set -euo pipefail
cd "$(dirname "${{BASH_SOURCE[0]}}")"
export PYTHONDONTWRITEBYTECODE=1
exec python3 -B -m unittest -v test_conformance
'''


# --- scaffold ------------------------------------------------------------------

def cmd_scaffold(args: argparse.Namespace) -> None:
    answers = load_answers(args.answers)
    name = args.connector or get(answers, "name")
    delivery = args.delivery or get(answers, "delivery")
    if not name or not NAME_RE.match(str(name)):
        refuse("name_invalid", detail="kebab-case, e.g. events-connector", name=name)
    if delivery not in DELIVERIES:
        refuse("delivery_unknown", detail=f"one of {list(DELIVERIES)}", delivery=delivery)
    root = Path(args.root or os.getcwd()).resolve()
    if not root.is_dir():
        refuse("root_missing", root=str(root))
    if delivery == "stream":
        connector = get(answers, "stream.connector")
        source = get(answers, "stream.source") or get(answers, "source.word") or ""
        if not connector:
            refuse("stream_connector_missing", detail="stream.connector names the installed connector that lists this source")
        emit({"outcome": "redirect", "connector": connector, "source": source,
              "connect": f"/daemon connect {connector} {source}".rstrip(),
              "why": "an installed event-stream connector already lists this source; no new connector is written",
              "written": []})
    plugin_id = args.plugin or (get(answers, "placement.plugin_id") if get(answers, "placement.kind") == "plugin" else None)
    if plugin_id and not NAME_RE.match(str(plugin_id)):
        refuse("plugin_id_invalid", plugin=plugin_id)
    fields, todo = fields_for(name, delivery, answers)
    module = fields["SCRIPT_NAME"]
    try:
        skill_md = render((TEMPLATES / "SKILL.md.tmpl").read_text(encoding="utf-8"), fields)
        script = render((TEMPLATES / "connector.py.tmpl").read_text(encoding="utf-8"), fields)
    except (OSError, KeyError) as exc:
        refuse("template_unavailable", detail=str(exc))

    # Relative targets -> contents. Every top-level target must be free.
    if plugin_id:
        skill_rel = Path("crates/plugins") / plugin_id / "skills" / name
        tests_rel = Path("crates/plugins/core-skill-tests") / plugin_id
        top_level = [Path("crates/plugins") / plugin_id, tests_rel, Path("changelog.d") / f"{name}.md"]
        script_expr = f'HERE.parent.parent / "{plugin_id}/skills/{name}/scripts/{module}"'
    else:
        skill_rel = Path(".agents/skills") / name
        tests_rel = skill_rel / "tests"
        top_level = [skill_rel]
        script_expr = f'HERE.parent / "scripts/{module}"'
    files: dict[Path, str] = {
        skill_rel / "SKILL.md": skill_md,
        skill_rel / "scripts" / module: script,
        tests_rel / "answers.json": json.dumps(dict(answers, name=name, delivery=delivery), indent=2, sort_keys=True) + "\n",
        tests_rel / "test_conformance.py": TEST_CONFORMANCE.format(
            name=name, script_expr=script_expr, source_word=fields["SOURCE_WORD"], env_prefix=fields["ENV_PREFIX"]),
        tests_rel / "run.sh": RUN_SH.format(name=name),
        tests_rel / "connector_conformance.py": CONFORMANCE.read_text(encoding="utf-8"),
    }
    if plugin_id:
        pkg = Path("crates/plugins") / plugin_id
        files[pkg / "plugin.json"] = plugin_manifest(plugin_id, name, fields["SOURCE_NAME"])
        files[pkg / "Cargo.toml"] = cargo_toml(plugin_id)
        files[pkg / "src/lib.rs"] = lib_rs(plugin_id, name, module)
        files[pkg / "tests/gate_posture.rs"] = gate_posture_rs(plugin_id, name, bool(fields["GATE_LINE"]))
        files[Path("changelog.d") / f"{name}.md"] = f"new: Added the `{name}` daemon connector for {fields['SOURCE_NAME']}\n"
    occupied = [str(t) for t in top_level if (root / t).exists()]
    if occupied:
        refuse("target_exists", occupied=occupied, root=str(root))

    # Staged UNDER the root, beside the targets: the same filesystem, so each
    # final move below is one atomic rename, never a copy that a crash could
    # leave half-done (FR-37480-44(e)).
    # Every target's parent must already be a directory (or creatable): a
    # regular file where `changelog.d/` should be is refused before anything
    # moves, never discovered after the first rename.
    for t in top_level:
        parent = root / t.parent
        if parent.exists() and not parent.is_dir():
            refuse("target_parent_not_a_directory", parent=str(t.parent), root=str(root))
    staging = Path(tempfile.mkdtemp(prefix=".connector-author-", dir=str(root)))
    moved: list[Path] = []
    try:
        for rel, content in files.items():
            dest = staging / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            if dest.suffix in (".py", ".sh"):
                dest.chmod(0o755)
        # Re-check right before the moves; then move each top-level target.
        occupied = [str(t) for t in top_level if (root / t).exists()]
        if occupied:
            refuse("target_exists", occupied=occupied, root=str(root))
        if os.environ.get("NEW_CONNECTOR_FAULT") == "before_move":
            # Test seam (INV-37480-44): a failure between the build and the moves
            # leaves nothing behind; the staging tree is removed by `finally`.
            refuse("fault_injected", where="before_move")
        try:
            for t in top_level:
                (root / t).parent.mkdir(parents=True, exist_ok=True)
                os.rename(str(staging / t), str(root / t))  # same filesystem: one atomic rename
                moved.append(t)
        except OSError as exc:
            # Transactional: put back what already moved; `finally` removes it
            # with the staging tree, so the root is byte-identical again.
            for t in reversed(moved):
                try:
                    os.rename(str(root / t), str(staging / t))
                except OSError:
                    pass
            refuse("move_failed", detail=str(exc), root=str(root))
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    check_cmd = f"python3 {HERE / 'new_connector.py'} check --skill-dir {root / skill_rel}"
    if plugin_id:
        check_cmd += f" --tests-dir {root / tests_rel}"
    emit({
        "outcome": "scaffolded", "connector": name, "delivery": delivery, "root": str(root),
        "skill_dir": str(root / skill_rel), "script": str(root / skill_rel / "scripts" / module),
        "tests_dir": str(root / tests_rel), "plugin": plugin_id,
        "written": sorted(str(p) for p in files),
        "todo": todo,
        "next": [check_cmd,
                 f"fill every TODO(answer …) in {skill_rel / 'scripts' / module} from tests/answers.json, then re-run check",
                 f"git checkout -b feat/connector-{name} && git add {' '.join(str(t) for t in top_level)} && git commit"]
                + ([f"register crates/plugins/{plugin_id} in the workspace Cargo.toml, the product composition roster and ci-impact-plan.sh (human-reviewed PR)",
                    f"Internal Buck build: the crate embeds non-Rust files, so add extra_srcs = [\"plugin.json\", \"skills/**\"] in fbcode/musecode/fixups/tbh-{plugin_id}/fixups.toml (Reindeer stages only *.rs)"] if plugin_id else []),
    })


# --- check ---------------------------------------------------------------------

RULE_RE = re.compile(r"^(?P<name>[a-z -]+): (?P<verdict>ok|FAIL) \((?P<detail>.*)\)$")


def status_contract(status_proc: subprocess.CompletedProcess, source: str) -> dict:
    """One `check` rule: `status --json` declares `sources_available` with the
    source word and a `listeners` record for every word in it."""
    try:
        status = json.loads(status_proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"ok": False, "detail": f"status exit {status_proc.returncode}: no JSON line"}
    available = status.get("sources_available")
    listeners = status.get("listeners")
    if not (isinstance(available, list) and available and all(isinstance(w, str) for w in available)):
        return {"ok": False, "detail": f"sources_available must be a non-empty list naming {source!r}; got {available!r}"}
    if source not in available:
        return {"ok": False, "detail": f"sources_available {available!r} lacks the source word {source!r}"}
    unrecorded = [w for w in available if not (isinstance(listeners, dict)
                                                and (listeners.get(w) or {}).get("listener") in ("live", "absent"))]
    if unrecorded:
        return {"ok": False, "detail": f"listeners carries no record for {unrecorded!r}"}
    return {"ok": True, "detail": f"sources_available {available!r}; one listeners record per word"}


def cmd_check(args: argparse.Namespace) -> None:
    skill_dir = Path(args.skill_dir).resolve()
    tests_dir = Path(args.tests_dir).resolve() if args.tests_dir else skill_dir / "tests"
    scripts = sorted((skill_dir / "scripts").glob("*.py")) if (skill_dir / "scripts").is_dir() else []
    if len(scripts) != 1:
        refuse("script_not_found", skill_dir=str(skill_dir), scripts=[s.name for s in scripts])
    script = scripts[0]
    answers_path = tests_dir / "answers.json"
    try:
        answers = json.loads(answers_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        refuse("answers_unreadable", path=str(answers_path), detail=str(exc))
    name = answers.get("name") or skill_dir.name
    source = get(answers, "source.word") or (name[:-len("-connector")] if name.endswith("-connector") else name)
    prefix = re.sub(r"[^A-Z0-9]", "_", str(name).upper()) + "_"
    rules: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="connector-check-") as tmp:
        fixture = Path(tmp) / "fixture.json"
        fixture.write_text(json.dumps({"inbound": {source: [
            {"id": "e1", "sender": "alice", "text": "@muse hello", "conversation": f"{source}:1"},
            # A real source's shapes: a multi-line text and a sender carrying ':' —
            # the template must still print exactly one feed line per message.
            {"id": "e2", "sender": "bob: ops", "text": "@muse first line\nsecond line", "conversation": f"{source}:2"}]}}))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        env[prefix + "FIXTURE_FILE"] = str(fixture)
        env[prefix + "STATE_DIR"] = str(Path(tmp) / "state")
        env[prefix + "POLL_S"] = "0.05"
        proc = subprocess.run([sys.executable, "-B", str(CONFORMANCE), str(script), "--listen", "--source", str(source),
                               "--reply-to", "c1"], capture_output=True, text=True, env=env, timeout=180, check=False)
        for line in proc.stdout.splitlines():
            m = RULE_RE.match(line.strip())
            if m:
                rules[m.group("name")] = {"ok": m.group("verdict") == "ok", "detail": m.group("detail")}
        # The status contract the daemon's `start` reads (#38715 D-META-2):
        # `sources_available` names the answers' source word and `listeners`
        # carries one record per word in it.
        status_proc = subprocess.run([sys.executable, "-B", str(script), "status", "--json"],
                                     capture_output=True, text=True, env=env, timeout=60, check=False)
        rules["status contract"] = status_contract(status_proc, str(source))
        conformance_ok = proc.returncode == 0 and rules and all(r["ok"] for r in rules.values())
    tests_exit = None
    if (tests_dir / "test_conformance.py").is_file():
        tests = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(tests_dir), "-t", str(tests_dir)],
                               capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                               timeout=300, check=False)
        tests_exit = tests.returncode
    ok = bool(conformance_ok) and tests_exit in (None, 0)
    emit({"outcome": "ok" if ok else "failed", "connector": name, "script": str(script), "rules": rules,
          "tests": {"dir": str(tests_dir), "exit": tests_exit},
          "conformance_stderr": proc.stderr.strip()[-400:] if not conformance_ok else ""}, 0 if ok else 1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="new_connector.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    scaffold = sub.add_parser("scaffold")
    scaffold.add_argument("--connector", default=None, help="the connector id (kebab-case)")
    scaffold.add_argument("--delivery", choices=DELIVERIES, default=None)
    scaffold.add_argument("--answers", required=True, help="interview answers JSON (a file, or - for stdin)")
    scaffold.add_argument("--plugin", default=None, help="plugin package id: write crates/plugins/<id>/ instead of a project skill")
    scaffold.add_argument("--root", default=None, help="workspace or repository root (default: cwd)")
    scaffold.set_defaults(func=cmd_scaffold)
    check = sub.add_parser("check")
    check.add_argument("--skill-dir", required=True)
    check.add_argument("--tests-dir", default=None, help="default <skill-dir>/tests")
    check.set_defaults(func=cmd_check)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
