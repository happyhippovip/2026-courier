import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.run_chief_relay_cycle import (
    fail,
    is_command_pending,
    discover_pending_command,
    run_cycle,
    main,
)

def test_fail():
    with pytest.raises(SystemExit) as excinfo:
        fail("Test error")
    assert "RELAY_CYCLE_ERROR: Test error" in str(excinfo.value)

def test_is_command_pending_invalid_json(tmp_path):
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text("{invalid json", encoding="utf-8")
    assert is_command_pending(cmd_file, tmp_path) is False

def test_is_command_pending_not_pending(tmp_path):
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps({
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "COMPLETED",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-123"
    }), encoding="utf-8")
    assert is_command_pending(cmd_file, tmp_path) is False

def test_is_command_pending_valid(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    
    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps({
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-123"
    }), encoding="utf-8")
    assert is_command_pending(cmd_file, processed_dir) is True

def test_is_command_pending_already_processed(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    proc_file = processed_dir / "proc.json"
    proc_file.write_text(json.dumps({"parent_id": "msg-123"}), encoding="utf-8")

    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps({
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-123"
    }), encoding="utf-8")
    assert is_command_pending(cmd_file, processed_dir) is False

def test_discover_pending_command_empty(tmp_path):
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    assert discover_pending_command(incoming, processed) is None

def test_discover_pending_command_found(tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    processed = tmp_path / "processed"
    processed.mkdir()

    cmd_file = incoming / "cmd.json"
    cmd_file.write_text(json.dumps({
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-123"
    }), encoding="utf-8")
    
    found = discover_pending_command(incoming, processed)
    assert found == cmd_file

def test_command_does_not_follow_a_symlink(tmp_path, monkeypatch):
    secret = {
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "SECRET-MSG",
        "task_id": "SECRET-TASK",
    }
    outside = tmp_path / "outside-cmd.json"
    outside.write_text(json.dumps(secret), encoding="utf-8")
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    link = incoming / "cmd.json"
    link.symlink_to(outside)
    processed = tmp_path / "processed"
    processed.mkdir()

    outside_dir = tmp_path / "outside-incoming"
    outside_dir.mkdir()
    (outside_dir / "cmd.json").write_text(json.dumps(secret), encoding="utf-8")
    linked_incoming = tmp_path / "linked-incoming"
    linked_incoming.symlink_to(outside_dir, target_is_directory=True)

    plain_incoming = tmp_path / "plain-incoming"
    plain_incoming.mkdir()
    plain = plain_incoming / "cmd.json"
    plain.write_text(json.dumps(secret), encoding="utf-8")

    def pending(path, folder):
        try:
            return ("ok", is_command_pending(path, folder))
        except SystemExit as exc:
            return ("err", str(exc))

    def discover(folder):
        try:
            found = discover_pending_command(folder, processed)
        except SystemExit as exc:
            return ("err", str(exc))
        if found is None:
            return ("ok", None, None)
        data = json.loads(found.read_text(encoding="utf-8"))
        return ("ok", found.name, data.get("message_id"))

    refused = "RELAY_CYCLE_ERROR: refusing to follow a symlink"
    file_result = pending(link, processed)
    dir_result = discover(linked_incoming)
    plain_result = pending(plain, processed)

    repo = tmp_path / "repo"
    (repo / "events").mkdir(parents=True)
    (repo / "events" / "incoming").symlink_to(outside_dir, target_is_directory=True)
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "--repo-dir", str(repo),
            "--incoming-dir", "events/incoming",
            "--disable-auto-memory",
        ],
    )
    try:
        main()
        cli_err = None
    except SystemExit as exc:
        cli_err = str(exc)

    assert (file_result, dir_result, plain_result, cli_err) == (
        ("err", refused),
        ("err", refused),
        ("ok", True),
        refused,
    )

def test_dispatch_dir_cli_does_not_follow_a_symlink(tmp_path, monkeypatch):
    secret = {
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "SECRET-MSG",
        "task_id": "SECRET-TASK",
    }

    class Dummy:
        returncode = 0
        stderr = ""
        stdout = ""

    def plant(name, link_dispatch):
        repo = tmp_path / name
        incoming = repo / "events" / "incoming"
        incoming.mkdir(parents=True)
        (incoming / "cmd.json").write_text(json.dumps(secret), encoding="utf-8")
        recorded = []

        def fake_run(cmd, *args, **kwargs):
            recorded.append(list(cmd))
            return Dummy()

        monkeypatch.setattr("scripts.run_chief_relay_cycle.subprocess.run", fake_run)
        monkeypatch.setattr(
            "sys.argv",
            [
                "prog",
                "--repo-dir", str(repo),
                "--incoming-dir", "events/incoming",
                "--dispatch-dir", str(link_dispatch),
                "--disable-auto-memory",
            ],
        )
        try:
            main()
            err = None
        except SystemExit as exc:
            err = str(exc)
        output_dirs = []
        for cmd in recorded:
            if "--output-dir" in cmd:
                output_dirs.append(cmd[cmd.index("--output-dir") + 1])
        return err, output_dirs

    outside = tmp_path / "outside-dispatch"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = tmp_path / "linked-dispatch"
    linked.symlink_to(outside, target_is_directory=True)
    err_link, outs_link = plant("repo-link", linked)

    parent_outside = tmp_path / "dispatch-parent-outside"
    parent_outside.mkdir()
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = tmp_path / "dispatch-linked-parent"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)
    err_parent, outs_parent = plant("repo-parent", linked_parent / "dispatch")

    plain = tmp_path / "plain-dispatch"
    err_plain, outs_plain = plant("repo-plain", plain)
    refused = "RELAY_CYCLE_ERROR: refusing to follow a symlink"
    assert (
        err_link,
        outs_link,
        sorted(p.name for p in outside.iterdir()),
        err_parent,
        outs_parent,
        sorted(p.name for p in parent_outside.iterdir()),
        err_plain,
        [Path(path).name for path in outs_plain],
    ) == (
        refused,
        [],
        ["keep.txt"],
        refused,
        [],
        ["keep.txt"],
        "RELAY_CYCLE_ERROR: Worker job file was not created: "
        + str((plain.resolve() / "SECRET-TASK-worker-job.json")),
        ["plain-dispatch"],
    )


def test_processed_dir_cli_does_not_follow_a_symlink(tmp_path, monkeypatch, capsys):
    secret = {
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "SECRET-MSG",
        "task_id": "SECRET-TASK",
    }
    result = {"parent_id": "SECRET-MSG", "body": "SECRET-RESULT"}

    class Dummy:
        returncode = 0
        stderr = ""
        stdout = ""

    def plant(name, link_processed):
        repo = tmp_path / name
        incoming = repo / "events" / "incoming"
        incoming.mkdir(parents=True)
        (incoming / "cmd.json").write_text(json.dumps(secret), encoding="utf-8")
        (repo / "events" / "dispatch").mkdir(parents=True)
        (repo / "memory").mkdir()
        monkeypatch.setattr("scripts.run_chief_relay_cycle.subprocess.run", lambda *args, **kwargs: Dummy())
        monkeypatch.setattr(
            "sys.argv",
            [
                "prog",
                "--repo-dir", str(repo),
                "--incoming-dir", "events/incoming",
                "--processed-dir", str(link_processed),
                "--dispatch-dir", str(repo / "events" / "dispatch"),
                "--memory-repo", str(repo / "memory"),
                "--disable-auto-memory",
            ],
        )
        try:
            main()
            err = None
        except SystemExit as exc:
            err = str(exc)
        out = capsys.readouterr().out
        return err, "IDLE" in out

    outside = tmp_path / "outside-processed"
    outside.mkdir()
    (outside / "result.json").write_text(json.dumps(result), encoding="utf-8")
    linked = tmp_path / "linked-processed"
    linked.symlink_to(outside, target_is_directory=True)
    err_link, idle_link = plant("repo-link", linked)

    parent_outside = tmp_path / "processed-parent-outside"
    (parent_outside / "processed").mkdir(parents=True)
    (parent_outside / "processed" / "result.json").write_text(json.dumps(result), encoding="utf-8")
    linked_parent = tmp_path / "processed-linked-parent"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)
    err_parent, idle_parent = plant("repo-parent", linked_parent / "processed")

    refused = "RELAY_CYCLE_ERROR: refusing to follow a symlink"
    assert (
        err_link,
        idle_link,
        "SECRET-RESULT" in (outside / "result.json").read_text(encoding="utf-8"),
        err_parent,
        idle_parent,
        "SECRET-RESULT" in (parent_outside / "processed" / "result.json").read_text(encoding="utf-8"),
    ) == (
        refused,
        False,
        True,
        refused,
        False,
        True,
    )


def test_memory_repo_cli_does_not_follow_a_symlink(tmp_path, monkeypatch):
    secret = {
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "SECRET-MSG",
        "task_id": "SECRET-TASK",
    }

    class Dummy:
        returncode = 0
        stderr = ""
        stdout = ""

    def plant(name, link_memory):
        repo = tmp_path / name
        incoming = repo / "events" / "incoming"
        incoming.mkdir(parents=True)
        (incoming / "cmd.json").write_text(json.dumps(secret), encoding="utf-8")
        (repo / "events" / "processed").mkdir(parents=True)
        (repo / "events" / "dispatch").mkdir(parents=True)
        recorded = []

        def fake_run(cmd, *args, **kwargs):
            recorded.append(list(cmd))
            return Dummy()

        monkeypatch.setattr("scripts.run_chief_relay_cycle.subprocess.run", fake_run)
        monkeypatch.setattr(
            "sys.argv",
            [
                "prog",
                "--repo-dir", str(repo),
                "--incoming-dir", "events/incoming",
                "--processed-dir", str(repo / "events" / "processed"),
                "--dispatch-dir", str(repo / "events" / "dispatch"),
                "--memory-repo", str(link_memory),
                "--disable-auto-memory",
            ],
        )
        try:
            main()
            err = None
        except SystemExit as exc:
            err = str(exc)
        memory_args = []
        for cmd in recorded:
            if "--memory-repo" in cmd:
                memory_args.append(cmd[cmd.index("--memory-repo") + 1])
        return err, memory_args

    outside = tmp_path / "outside-memory"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = tmp_path / "linked-memory"
    linked.symlink_to(outside, target_is_directory=True)
    err_link, mem_link = plant("repo-link", linked)

    parent_outside = tmp_path / "memory-parent-outside"
    (parent_outside / "memory").mkdir(parents=True)
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = tmp_path / "memory-linked-parent"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)
    err_parent, mem_parent = plant("repo-parent", linked_parent / "memory")

    plain = tmp_path / "plain-memory"
    plain.mkdir()
    err_plain, mem_plain = plant("repo-plain", plain)
    refused = "RELAY_CYCLE_ERROR: refusing to follow a symlink"
    assert (
        err_link,
        mem_link,
        sorted(p.name for p in outside.iterdir()),
        err_parent,
        mem_parent,
        sorted(p.name for p in parent_outside.iterdir()),
        err_plain,
        mem_plain,
    ) == (
        refused,
        [],
        ["keep.txt"],
        refused,
        [],
        ["keep.txt", "memory"],
        "RELAY_CYCLE_ERROR: Worker job file was not created: "
        + str((tmp_path / "repo-plain" / "events" / "dispatch").resolve() / "SECRET-TASK-worker-job.json"),
        [str(plain.resolve())],
    )


def test_proposals_dir_cli_does_not_follow_a_symlink(tmp_path, monkeypatch):
    secret = {
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "SECRET-MSG",
        "task_id": "SECRET-TASK",
    }

    class Dummy:
        returncode = 0
        stderr = ""
        stdout = ""

    def plant(name, link_proposals):
        repo = tmp_path / name
        incoming = repo / "events" / "incoming"
        incoming.mkdir(parents=True)
        (incoming / "cmd.json").write_text(json.dumps(secret), encoding="utf-8")
        processed = repo / "events" / "processed"
        dispatch = repo / "events" / "dispatch"
        processed.mkdir(parents=True)
        dispatch.mkdir(parents=True)
        memory = repo / "memory"
        memory.mkdir()
        recorded = []

        def fake_run(cmd, *args, **kwargs):
            recorded.append(list(cmd))
            text = " ".join(str(part) for part in cmd)
            if "build_antigravity_worker_job.py" in text and "--command" in text:
                (dispatch / "SECRET-TASK-worker-job.json").write_text("{}", encoding="utf-8")
            if "consume_chief_command.py" in text:
                (processed / "SECRET-TASK-result.json").write_text("{}", encoding="utf-8")
            return Dummy()

        monkeypatch.setattr("scripts.run_chief_relay_cycle.subprocess.run", fake_run)
        monkeypatch.setattr(
            "sys.argv",
            [
                "prog",
                "--repo-dir", str(repo),
                "--incoming-dir", "events/incoming",
                "--processed-dir", str(processed),
                "--dispatch-dir", str(dispatch),
                "--proposals-dir", str(link_proposals),
                "--memory-repo", str(memory),
            ],
        )
        try:
            main()
            err = None
        except SystemExit as exc:
            err = str(exc)
        output_dirs = []
        for cmd in recorded:
            if any("build_memory_update_proposal.py" in str(part) for part in cmd) and "--output-dir" in cmd:
                output_dirs.append(cmd[cmd.index("--output-dir") + 1])
        return err, output_dirs

    outside = tmp_path / "outside-proposals"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = tmp_path / "linked-proposals"
    linked.symlink_to(outside, target_is_directory=True)
    err_link, outs_link = plant("repo-link", linked)

    parent_outside = tmp_path / "proposals-parent-outside"
    (parent_outside / "proposals").mkdir(parents=True)
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = tmp_path / "proposals-linked-parent"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)
    err_parent, outs_parent = plant("repo-parent", linked_parent / "proposals")

    plain = tmp_path / "plain-proposals"
    plain.mkdir()
    err_plain, outs_plain = plant("repo-plain", plain)
    refused = "RELAY_CYCLE_ERROR: refusing to follow a symlink"
    missing = "RELAY_CYCLE_ERROR: Proposal file was not created: "
    assert (
        err_link,
        outs_link,
        sorted(p.name for p in outside.iterdir()),
        err_parent,
        outs_parent,
        sorted(p.name for p in parent_outside.iterdir()),
        err_plain,
        outs_plain,
    ) == (
        refused,
        [],
        ["keep.txt"],
        refused,
        [],
        ["keep.txt", "proposals"],
        missing + str(plain.resolve() / "SECRET-TASK-memory-proposal.json"),
        [str(plain.resolve())],
    )


def test_decisions_dir_cli_does_not_follow_a_symlink(tmp_path, monkeypatch):
    secret = {
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "SECRET-MSG",
        "task_id": "SECRET-TASK",
    }

    class Dummy:
        returncode = 0
        stderr = ""
        stdout = ""

    def plant(name, link_decisions):
        repo = tmp_path / name
        incoming = repo / "events" / "incoming"
        incoming.mkdir(parents=True)
        (incoming / "cmd.json").write_text(json.dumps(secret), encoding="utf-8")
        processed = repo / "events" / "processed"
        dispatch = repo / "events" / "dispatch"
        proposals = repo / "events" / "proposals"
        processed.mkdir(parents=True)
        dispatch.mkdir(parents=True)
        proposals.mkdir(parents=True)
        memory = repo / "memory"
        memory.mkdir()
        recorded = []

        def fake_run(cmd, *args, **kwargs):
            recorded.append(list(cmd))
            text = " ".join(str(part) for part in cmd)
            if "build_antigravity_worker_job.py" in text and "--command" in text:
                (dispatch / "SECRET-TASK-worker-job.json").write_text("{}", encoding="utf-8")
            if "consume_chief_command.py" in text:
                (processed / "SECRET-TASK-result.json").write_text("{}", encoding="utf-8")
            if "build_memory_update_proposal.py" in text:
                (proposals / "SECRET-TASK-memory-proposal.json").write_text("{}", encoding="utf-8")
            return Dummy()

        monkeypatch.setattr("scripts.run_chief_relay_cycle.subprocess.run", fake_run)
        monkeypatch.setattr(
            "sys.argv",
            [
                "prog",
                "--repo-dir", str(repo),
                "--incoming-dir", "events/incoming",
                "--processed-dir", str(processed),
                "--dispatch-dir", str(dispatch),
                "--proposals-dir", str(proposals),
                "--decisions-dir", str(link_decisions),
                "--memory-repo", str(memory),
            ],
        )
        try:
            main()
            err = None
        except SystemExit as exc:
            err = str(exc)
        decision_dirs = []
        for cmd in recorded:
            if any("evaluate_memory_proposal_for_auto_approval.py" in str(part) for part in cmd) and "--output-decisions" in cmd:
                decision_dirs.append(cmd[cmd.index("--output-decisions") + 1])
        return err, decision_dirs

    outside = tmp_path / "outside-decisions"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = tmp_path / "linked-decisions"
    linked.symlink_to(outside, target_is_directory=True)
    err_link, dirs_link = plant("repo-link", linked)

    parent_outside = tmp_path / "decisions-parent-outside"
    (parent_outside / "decisions").mkdir(parents=True)
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = tmp_path / "decisions-linked-parent"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)
    err_parent, dirs_parent = plant("repo-parent", linked_parent / "decisions")

    plain = tmp_path / "plain-decisions"
    plain.mkdir()
    err_plain, dirs_plain = plant("repo-plain", plain)
    refused = "RELAY_CYCLE_ERROR: refusing to follow a symlink"
    missing = "RELAY_CYCLE_ERROR: Decision file was not created: "
    assert (
        err_link,
        dirs_link,
        sorted(p.name for p in outside.iterdir()),
        err_parent,
        dirs_parent,
        sorted(p.name for p in parent_outside.iterdir()),
        err_plain,
        dirs_plain,
    ) == (
        refused,
        [],
        ["keep.txt"],
        refused,
        [],
        ["decisions", "keep.txt"],
        missing + str(plain.resolve() / "SECRET-TASK-chief-decision.json"),
        [str(plain.resolve())],
    )


def test_approvals_dir_cli_does_not_follow_a_symlink(tmp_path, monkeypatch):
    secret = {
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "SECRET-MSG",
        "task_id": "SECRET-TASK",
    }

    class Dummy:
        returncode = 0
        stderr = ""
        stdout = ""

    def plant(name, link_approvals):
        repo = tmp_path / name
        incoming = repo / "events" / "incoming"
        incoming.mkdir(parents=True)
        (incoming / "cmd.json").write_text(json.dumps(secret), encoding="utf-8")
        processed = repo / "events" / "processed"
        dispatch = repo / "events" / "dispatch"
        proposals = repo / "events" / "proposals"
        decisions = repo / "events" / "decisions"
        for folder in (processed, dispatch, proposals, decisions):
            folder.mkdir(parents=True)
        memory = repo / "memory"
        memory.mkdir()
        recorded = []

        def fake_run(cmd, *args, **kwargs):
            recorded.append(list(cmd))
            text = " ".join(str(part) for part in cmd)
            if "build_antigravity_worker_job.py" in text and "--command" in text:
                (dispatch / "SECRET-TASK-worker-job.json").write_text("{}", encoding="utf-8")
            if "consume_chief_command.py" in text:
                (processed / "SECRET-TASK-result.json").write_text("{}", encoding="utf-8")
            if "build_memory_update_proposal.py" in text:
                (proposals / "SECRET-TASK-memory-proposal.json").write_text("{}", encoding="utf-8")
            if "evaluate_memory_proposal_for_auto_approval.py" in text:
                (decisions / "SECRET-TASK-chief-decision.json").write_text(
                    json.dumps({"decision": "AUTO_APPROVE", "reason_codes": []}),
                    encoding="utf-8",
                )
            return Dummy()

        monkeypatch.setattr("scripts.run_chief_relay_cycle.subprocess.run", fake_run)
        monkeypatch.setattr(
            "sys.argv",
            [
                "prog",
                "--repo-dir", str(repo),
                "--incoming-dir", "events/incoming",
                "--processed-dir", str(processed),
                "--dispatch-dir", str(dispatch),
                "--proposals-dir", str(proposals),
                "--decisions-dir", str(decisions),
                "--approvals-dir", str(link_approvals),
                "--memory-repo", str(memory),
            ],
        )
        try:
            main()
            err = None
        except SystemExit as exc:
            err = str(exc)
        approval_dirs = []
        for cmd in recorded:
            if any("evaluate_memory_proposal_for_auto_approval.py" in str(part) for part in cmd) and "--output-approvals" in cmd:
                approval_dirs.append(cmd[cmd.index("--output-approvals") + 1])
        return err, approval_dirs

    outside = tmp_path / "outside-approvals"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = tmp_path / "linked-approvals"
    linked.symlink_to(outside, target_is_directory=True)
    err_link, dirs_link = plant("repo-link", linked)

    parent_outside = tmp_path / "approvals-parent-outside"
    (parent_outside / "approvals").mkdir(parents=True)
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = tmp_path / "approvals-linked-parent"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)
    err_parent, dirs_parent = plant("repo-parent", linked_parent / "approvals")

    plain = tmp_path / "plain-approvals"
    plain.mkdir()
    err_plain, dirs_plain = plant("repo-plain", plain)
    refused = "RELAY_CYCLE_ERROR: refusing to follow a symlink"
    missing = "RELAY_CYCLE_ERROR: Auto-approval file was not created: "
    assert (
        err_link,
        dirs_link,
        sorted(p.name for p in outside.iterdir()),
        err_parent,
        dirs_parent,
        sorted(p.name for p in parent_outside.iterdir()),
        err_plain,
        dirs_plain,
    ) == (
        refused,
        [],
        ["keep.txt"],
        refused,
        [],
        ["approvals", "keep.txt"],
        missing + str(plain.resolve() / "SECRET-TASK-auto-approval.json"),
        [str(plain.resolve())],
    )


@patch("scripts.run_chief_relay_cycle.subprocess.run")
def test_run_cycle_no_pending(mock_run, tmp_path):
    res = run_cycle(
        repo_dir=tmp_path,
        incoming_dir=tmp_path / "incoming",
        processed_dir=tmp_path / "processed",
        dispatch_dir=tmp_path / "dispatch",
        memory_repo=None,
    )
    assert res["status"] == "IDLE"

@patch("scripts.run_chief_relay_cycle.subprocess.run")
def test_run_cycle_full_success(mock_run, tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    processed = tmp_path / "processed"
    processed.mkdir()
    dispatch = tmp_path / "dispatch"
    dispatch.mkdir()
    proposals = tmp_path / "proposals"
    proposals.mkdir()
    approvals = tmp_path / "approvals"
    approvals.mkdir()
    decisions = tmp_path / "decisions"
    decisions.mkdir()
    
    memory_repo = tmp_path / "memory_repo"
    memory_repo.mkdir()

    # Create pending command
    cmd_file = incoming / "cmd.json"
    cmd_file.write_text(json.dumps({
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-123",
        "task_id": "task-1"
    }), encoding="utf-8")

    def mock_subprocess_run(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str and "--validate" not in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        if "build_antigravity_worker_job.py" in cmd_str and "--validate" in cmd_str:
            return MagicMock(returncode=0)
        if "consume_chief_command.py" in cmd_str:
            (processed / "task-1-result.json").write_text("{}")
            return MagicMock(returncode=0)
        if "validate_chief_relay.py" in cmd_str:
            return MagicMock(returncode=0)
        if "build_memory_update_proposal.py" in cmd_str:
            (proposals / "task-1-memory-proposal.json").write_text("{}")
            return MagicMock(returncode=0)
        if "evaluate_memory_proposal_for_auto_approval.py" in cmd_str:
            (decisions / "task-1-chief-decision.json").write_text(json.dumps({"decision": "AUTO_APPROVE", "reason_codes": []}))
            (approvals / "task-1-auto-approval.json").write_text("{}")
            return MagicMock(returncode=0)
        if "apply_memory_update_proposal.py" in cmd_str:
            return MagicMock(returncode=0, stdout='{"success": true}')
        if "git" in cmd_str:
            return MagicMock(returncode=0, stdout='abcdef123')
        return MagicMock(returncode=0) # default

    mock_run.side_effect = mock_subprocess_run

    res = run_cycle(
        repo_dir=tmp_path,
        incoming_dir=incoming,
        processed_dir=processed,
        dispatch_dir=dispatch,
        proposals_dir=proposals,
        approvals_dir=approvals,
        decisions_dir=decisions,
        memory_repo=memory_repo,
        pull=True,
        push=True,
    )
    
    assert res["status"] == "COMPLETED"
    assert res["task_id"] == "task-1"
    assert res["memory_cycle"]["decision"] == "AUTO_APPROVE"
    assert res["commit_sha"] == "abcdef123"

@patch("scripts.run_chief_relay_cycle.subprocess.run")
def test_run_cycle_subprocess_failure(mock_run, tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    processed = tmp_path / "processed"
    processed.mkdir()
    dispatch = tmp_path / "dispatch"
    dispatch.mkdir()

    cmd_file = incoming / "cmd.json"
    cmd_file.write_text(json.dumps({
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-123",
        "task_id": "task-1"
    }), encoding="utf-8")

    # Mock builder failure
    mock_run.return_value = MagicMock(returncode=1, stderr="Boom")
    with pytest.raises(SystemExit) as excinfo:
        run_cycle(
            repo_dir=tmp_path,
            incoming_dir=incoming,
            processed_dir=processed,
            dispatch_dir=dispatch,
        )
    assert "Worker job builder failed: Boom" in str(excinfo.value)
    
    # Mock validate job failure
    def mock_val_job(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str and "--validate" not in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        return MagicMock(returncode=1, stderr="Val error")
    mock_run.side_effect = mock_val_job
    with pytest.raises(SystemExit) as excinfo:
        run_cycle(
            repo_dir=tmp_path,
            incoming_dir=incoming,
            processed_dir=processed,
            dispatch_dir=dispatch,
        )
    assert "Worker job JSON Schema validation failed: Val error" in str(excinfo.value)

    # Mock consumer failure
    def mock_consumer(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        return MagicMock(returncode=1, stderr="Consume error")
    mock_run.side_effect = mock_consumer
    with pytest.raises(SystemExit) as excinfo:
        run_cycle(
            repo_dir=tmp_path,
            incoming_dir=incoming,
            processed_dir=processed,
            dispatch_dir=dispatch,
        )
    assert "Consumer failed: Consume error" in str(excinfo.value)

    # Mock val failure
    def mock_val_relay(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        if "consume_chief_command.py" in cmd_str:
            (processed / "task-1-result.json").write_text("{}")
            return MagicMock(returncode=0)
        return MagicMock(returncode=1, stderr="Relay error")
    mock_run.side_effect = mock_val_relay
    with pytest.raises(SystemExit) as excinfo:
        run_cycle(
            repo_dir=tmp_path,
            incoming_dir=incoming,
            processed_dir=processed,
            dispatch_dir=dispatch,
        )
    assert "Result validation failed: Relay error" in str(excinfo.value)

    # Mock proposal builder failure
    def mock_prop_builder(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        if "consume_chief_command.py" in cmd_str:
            (processed / "task-1-result.json").write_text("{}")
            return MagicMock(returncode=0)
        if "validate_chief_relay.py" in cmd_str:
            return MagicMock(returncode=0)
        return MagicMock(returncode=1, stderr="Prop error")
    mock_run.side_effect = mock_prop_builder
    memory_repo = tmp_path / "memory"
    memory_repo.mkdir()
    with pytest.raises(SystemExit) as excinfo:
        run_cycle(
            repo_dir=tmp_path,
            incoming_dir=incoming,
            processed_dir=processed,
            dispatch_dir=dispatch,
            memory_repo=memory_repo
        )
    assert "Memory proposal builder failed: Prop error" in str(excinfo.value)

    # Mock evaluate memory proposal failure
    proposals = tmp_path / "proposals"
    proposals.mkdir()
    def mock_evaluate_memory(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        if "consume_chief_command.py" in cmd_str:
            (processed / "task-1-result.json").write_text("{}")
            return MagicMock(returncode=0)
        if "validate_chief_relay.py" in cmd_str:
            return MagicMock(returncode=0)
        if "build_memory_update_proposal.py" in cmd_str:
            (proposals / "task-1-memory-proposal.json").write_text("{}")
            return MagicMock(returncode=0)
        return MagicMock(returncode=1, stderr="Eval error")
    mock_run.side_effect = mock_evaluate_memory
    with pytest.raises(SystemExit) as excinfo:
        run_cycle(
            repo_dir=tmp_path,
            incoming_dir=incoming,
            processed_dir=processed,
            dispatch_dir=dispatch,
            proposals_dir=proposals,
            memory_repo=memory_repo
        )
    assert "Autonomous Chief Policy evaluation failed: Eval error" in str(excinfo.value)

    # Mock apply memory update proposal failure
    decisions = tmp_path / "decisions"
    decisions.mkdir()
    approvals = tmp_path / "approvals"
    approvals.mkdir()
    def mock_apply_memory(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        if "consume_chief_command.py" in cmd_str:
            (processed / "task-1-result.json").write_text("{}")
            return MagicMock(returncode=0)
        if "validate_chief_relay.py" in cmd_str:
            return MagicMock(returncode=0)
        if "build_memory_update_proposal.py" in cmd_str:
            (proposals / "task-1-memory-proposal.json").write_text("{}")
            return MagicMock(returncode=0)
        if "evaluate_memory_proposal_for_auto_approval.py" in cmd_str:
            (decisions / "task-1-chief-decision.json").write_text(json.dumps({"decision": "AUTO_APPROVE", "reason_codes": []}))
            (approvals / "task-1-auto-approval.json").write_text("{}")
            return MagicMock(returncode=0)
        if "apply_memory_update_proposal.py" in cmd_str:
            return MagicMock(returncode=1, stderr="Apply error")
        return MagicMock(returncode=0)
    mock_run.side_effect = mock_apply_memory
    with pytest.raises(SystemExit) as excinfo:
        run_cycle(
            repo_dir=tmp_path,
            incoming_dir=incoming,
            processed_dir=processed,
            dispatch_dir=dispatch,
            proposals_dir=proposals,
            decisions_dir=decisions,
            approvals_dir=approvals,
            memory_repo=memory_repo
        )
    assert "Memory write handler failed: Apply error" in str(excinfo.value)



    # Mock git push failure
    def mock_git_push(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        if "consume_chief_command.py" in cmd_str:
            (processed / "task-1-result.json").write_text("{}")
            return MagicMock(returncode=0)
        if "validate_chief_relay.py" in cmd_str:
            return MagicMock(returncode=0)
        if "build_memory_update_proposal.py" in cmd_str:
            (proposals / "task-1-memory-proposal.json").write_text("{}")
            return MagicMock(returncode=0)
        if "evaluate_memory_proposal_for_auto_approval.py" in cmd_str:
            (decisions / "task-1-chief-decision.json").write_text(json.dumps({"decision": "AUTO_APPROVE", "reason_codes": []}))
            (approvals / "task-1-auto-approval.json").write_text("{}")
            return MagicMock(returncode=0)
        if "apply_memory_update_proposal.py" in cmd_str:
            return MagicMock(returncode=0, stdout='{"success": true}')
        if "git" in cmd_str and "push" in cmd_str:
            return MagicMock(returncode=1, stderr="Git Push Error")
        return MagicMock(returncode=0)
    mock_run.side_effect = mock_git_push
    with pytest.raises(SystemExit) as excinfo:
        run_cycle(
            repo_dir=tmp_path,
            incoming_dir=incoming,
            processed_dir=processed,
            dispatch_dir=dispatch,
            proposals_dir=proposals,
            decisions_dir=decisions,
            approvals_dir=approvals,
            memory_repo=memory_repo,
            push=True
        )
    assert "Git push failed: Git Push Error" in str(excinfo.value)

def test_is_command_pending_invalid_fields(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    cmd_file = tmp_path / "cmd.json"

    # wrong schema_version
    cmd_file.write_text(json.dumps({"schema_version": "1.0", "type": "COMMAND", "status": "NEW", "source": "chief", "destination": "antigravity", "message_id": "123"}), encoding="utf-8")
    assert is_command_pending(cmd_file, processed_dir) is False

    # wrong type
    cmd_file.write_text(json.dumps({"schema_version": "2.0", "type": "RESULT", "status": "NEW", "source": "chief", "destination": "antigravity", "message_id": "123"}), encoding="utf-8")
    assert is_command_pending(cmd_file, processed_dir) is False

    # wrong source
    cmd_file.write_text(json.dumps({"schema_version": "2.0", "type": "COMMAND", "status": "NEW", "source": "other", "destination": "antigravity", "message_id": "123"}), encoding="utf-8")
    assert is_command_pending(cmd_file, processed_dir) is False

    # missing message_id
    cmd_file.write_text(json.dumps({"schema_version": "2.0", "type": "COMMAND", "status": "NEW", "source": "chief", "destination": "antigravity"}), encoding="utf-8")
    assert is_command_pending(cmd_file, processed_dir) is False

def test_is_command_pending_corrupt_processed(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    proc_file = processed_dir / "proc.json"
    proc_file.write_text("{bad json", encoding="utf-8")

    cmd_file = tmp_path / "cmd.json"
    cmd_file.write_text(json.dumps({
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-123"
    }), encoding="utf-8")
    assert is_command_pending(cmd_file, processed_dir) is True

@patch("scripts.run_chief_relay_cycle.subprocess.run")
def test_run_cycle_pull_warning(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=1, stderr="Pull warning")
    res = run_cycle(
        repo_dir=tmp_path,
        incoming_dir=tmp_path / "incoming",
        processed_dir=tmp_path / "processed",
        dispatch_dir=tmp_path / "dispatch",
        pull=True
    )
    assert res["status"] == "IDLE"

@patch("scripts.run_chief_relay_cycle.subprocess.run")
def test_run_cycle_dry_run(mock_run, tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    processed = tmp_path / "processed"
    processed.mkdir()
    dispatch = tmp_path / "dispatch"
    dispatch.mkdir()
    proposals = tmp_path / "proposals"
    proposals.mkdir()
    approvals = tmp_path / "approvals"
    approvals.mkdir()
    decisions = tmp_path / "decisions"
    decisions.mkdir()
    memory_repo = tmp_path / "memory_repo"
    memory_repo.mkdir()

    cmd_file = incoming / "cmd.json"
    cmd_file.write_text(json.dumps({
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": "msg-123",
        "task_id": "task-1"
    }), encoding="utf-8")

    def mock_subprocess_run(args, **kwargs):
        cmd_str = " ".join(args)
        if "build_antigravity_worker_job.py" in cmd_str and "--validate" not in cmd_str:
            (dispatch / "task-1-worker-job.json").write_text("{}")
            return MagicMock(returncode=0)
        if "build_antigravity_worker_job.py" in cmd_str and "--validate" in cmd_str:
            return MagicMock(returncode=0)
        if "consume_chief_command.py" in cmd_str:
            (processed / "task-1-result.json").write_text("{}")
            return MagicMock(returncode=0)
        if "validate_chief_relay.py" in cmd_str:
            return MagicMock(returncode=0)
        if "build_memory_update_proposal.py" in cmd_str:
            (proposals / "task-1-memory-proposal.json").write_text("{}")
            return MagicMock(returncode=0)
        if "evaluate_memory_proposal_for_auto_approval.py" in cmd_str:
            (decisions / "task-1-chief-decision.json").write_text(json.dumps({"decision": "AUTO_APPROVE", "reason_codes": []}))
            (approvals / "task-1-auto-approval.json").write_text("{}")
            return MagicMock(returncode=0)
        if "apply_memory_update_proposal.py" in cmd_str:
            assert "--dry-run" in args
            return MagicMock(returncode=0, stdout='{"success": true, "dry_run": true}')
        return MagicMock(returncode=0)

    mock_run.side_effect = mock_subprocess_run

    res = run_cycle(
        repo_dir=tmp_path,
        incoming_dir=incoming,
        processed_dir=processed,
        dispatch_dir=dispatch,
        proposals_dir=proposals,
        approvals_dir=approvals,
        decisions_dir=decisions,
        memory_repo=memory_repo,
        memory_dry_run=True,
    )
    assert res["memory_cycle"]["write_result"] == {"success": True, "dry_run": True}


def _pending_command(task_id: str, message_id: str) -> dict:
    return {
        "schema_version": "2.0",
        "type": "COMMAND",
        "status": "NEW",
        "source": "chief",
        "destination": "antigravity",
        "message_id": message_id,
        "task_id": task_id,
    }


@patch("scripts.run_chief_relay_cycle.subprocess.run")
def test_unverified_execution_does_not_end_before_next_command(mock_run, tmp_path, monkeypatch, capsys):
    """A DONE/PASS claim that only records validation is not completion.

    The same cycle must still hand the next distinct pending command to the
    existing discover/run path instead of stopping after that claim.
    """
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    dispatch = tmp_path / "dispatch"
    for directory in (incoming, processed, dispatch):
        directory.mkdir()

    first = incoming / "a.json"
    second = incoming / "b.json"
    first.write_text(json.dumps(_pending_command("task-1", "msg-1")), encoding="utf-8")
    second.write_text(json.dumps(_pending_command("task-2", "msg-2")), encoding="utf-8")
    os_utime = __import__("os").utime
    os_utime(first, (1, 1_000))
    os_utime(second, (1, 2_000))

    def ids_from(args):
        command_path = Path(args[args.index("--command") + 1])
        data = json.loads(command_path.read_text(encoding="utf-8"))
        return data["task_id"], data["message_id"]

    def mock_subprocess_run(args, **kwargs):
        cmd_str = " ".join(str(part) for part in args)
        if "build_antigravity_worker_job.py" in cmd_str and "--validate" not in cmd_str:
            task_id, _message_id = ids_from(args)
            (dispatch / f"{task_id}-worker-job.json").write_text("{}", encoding="utf-8")
            return MagicMock(returncode=0, stderr="", stdout="")
        if "consume_chief_command.py" in cmd_str:
            task_id, message_id = ids_from(args)
            if task_id == "task-1":
                record = {
                    "status": "DONE",
                    "task_id": task_id,
                    "message_id": f"result-{message_id}",
                    "parent_id": message_id,
                    "payload": {
                        "summary": f"Executed Chief Command: echo {task_id}",
                        "test_results": "PASS",
                        "verified_facts": [f"Command validated successfully: id={message_id}"],
                    },
                }
                code = 0
            else:
                record = {
                    "status": "BLOCKED",
                    "task_id": task_id,
                    "message_id": f"result-{message_id}",
                    "parent_id": message_id,
                    "payload": {
                        "summary": f"Command not executed: echo {task_id}",
                        "test_results": "NOT_RUN",
                        "verified_facts": ["The command was not run"],
                    },
                }
                code = 1
            (processed / f"{task_id}-result.json").write_text(json.dumps(record), encoding="utf-8")
            return MagicMock(returncode=code, stderr="", stdout="")
        return MagicMock(returncode=0, stderr="", stdout="")

    mock_run.side_effect = mock_subprocess_run
    monkeypatch.setattr("sys.argv", [
        "run_chief_relay_cycle.py",
        "--repo-dir", str(tmp_path),
        "--incoming-dir", "incoming",
        "--processed-dir", "processed",
        "--dispatch-dir", "dispatch",
        "--disable-auto-memory",
        "--memory-repo", str(tmp_path / "missing-memory"),
    ])

    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 1

    reported = json.loads(capsys.readouterr().out)
    items = reported if isinstance(reported, list) else [reported]
    by_task = {item.get("task_id"): item for item in items if item.get("task_id")}
    assert "task-1" in by_task and "task-2" in by_task
    assert by_task["task-1"]["status"] != "COMPLETED"
    assert by_task["task-2"]["status"] != "COMPLETED"

