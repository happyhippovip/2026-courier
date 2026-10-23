from scripts.run_content_production_pipeline import execute_script_stage


def _run(stage):
    try:
        execute_script_stage(stage, "fruit", "demo")
    except ValueError as exc:
        return str(exc)
    return None


def test_content_script_does_not_follow_a_symlink(tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("SECRET-SCRIPT", encoding="utf-8")
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "script.md").symlink_to(outside)
    file_err = _run(stage)
    leaked = outside.read_text(encoding="utf-8")
    file_mark = "SECRET-SCRIPT" if leaked == "SECRET-SCRIPT" else leaked.splitlines()[0]

    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (outside_dir / "keep.txt").write_text("SECRET-DIR", encoding="utf-8")
    linked = tmp_path / "linked-stage"
    linked.symlink_to(outside_dir)
    parent_err = _run(linked)

    local = tmp_path / "local-stage"
    local.mkdir()
    local_err = _run(local)
    local_text = (
        (local / "script.md").read_text(encoding="utf-8")
        if (local / "script.md").exists()
        else ""
    )

    assert (
        file_err,
        file_mark,
        parent_err,
        (outside_dir / "script.md").exists(),
        (outside_dir / "keep.txt").read_text(encoding="utf-8"),
        local_err,
        "Script:" in local_text,
    ) == (
        "refusing to follow a symlink",
        "SECRET-SCRIPT",
        "refusing to follow a symlink",
        False,
        "SECRET-DIR",
        None,
        True,
    )
