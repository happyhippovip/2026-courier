import json
import sys

from run_thought_memory_mesh import load_json, main


def _load(path):
    try:
        return ("loaded", load_json(path, {}))
    except ValueError as exc:
        return ("raised", str(exc))


def _write(monkeypatch, messages, ledger, output, memory):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_thought_memory_mesh.py",
            "--messages",
            str(messages),
            "--ledger",
            str(ledger),
            "--output",
            str(output),
            "--memory-repo",
            str(memory),
        ],
    )
    try:
        main()
    except ValueError as exc:
        return str(exc)
    return None


def test_mesh_paths_do_not_follow_a_symlink(tmp_path, monkeypatch):
    outside = tmp_path / "outside-messages.json"
    outside.write_text(json.dumps({"secret": "SECRET-MESH"}), encoding="utf-8")
    file_link = tmp_path / "messages-link.json"
    file_link.symlink_to(outside)
    file_seen = _load(file_link)

    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    dir_spec = outside_dir / "messages.json"
    dir_spec.write_text(json.dumps({"secret": "SECRET-DIR"}), encoding="utf-8")
    linked_parent = tmp_path / "inbox"
    linked_parent.symlink_to(outside_dir)
    parent_seen = _load(linked_parent / "messages.json")

    messages = tmp_path / "messages.json"
    messages.write_text("[]", encoding="utf-8")
    memory = tmp_path / "memory"
    memory.mkdir()

    ledger_outside = tmp_path / "ledger-outside.json"
    ledger_outside.write_text(
        json.dumps({"secret": "SECRET-LEDGER"}),
        encoding="utf-8",
    )
    ledger_link = tmp_path / "ledger.json"
    ledger_link.symlink_to(ledger_outside)
    ledger_output = tmp_path / "ledger-output.json"
    ledger_err = _write(monkeypatch, messages, ledger_link, ledger_output, memory)

    output_outside = tmp_path / "output-outside.json"
    output_outside.write_text("SECRET-OUTPUT", encoding="utf-8")
    output_link = tmp_path / "output.json"
    output_link.symlink_to(output_outside)
    output_ledger = tmp_path / "output-ledger.json"
    output_err = _write(monkeypatch, messages, output_ledger, output_link, memory)

    ledger_text = ledger_outside.read_text(encoding="utf-8")
    output_text = output_outside.read_text(encoding="utf-8")
    assert (
        file_seen,
        parent_seen,
        ledger_err,
        "SECRET-LEDGER" in ledger_text,
        output_err,
        "SECRET-OUTPUT" in output_text,
    ) == (
        ("raised", "refusing to follow a symlink"),
        ("raised", "refusing to follow a symlink"),
        "refusing to follow a symlink",
        True,
        "refusing to follow a symlink",
        True,
    )
