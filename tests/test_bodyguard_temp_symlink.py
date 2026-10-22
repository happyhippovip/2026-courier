from scripts.run_bodyguards import BodyguardPoolManager


def test_bodyguard_temp_does_not_follow_a_symlink(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("SECRET-TMP", encoding="utf-8")
    manager = BodyguardPoolManager(tmp_path / "repo")
    link = manager.states_dir / "agent-bodyguard-alpha.tmp"
    link.symlink_to(outside)
    try:
        manager.initialize_pool()
        err = None
    except ValueError as exc:
        err = str(exc)
    leaked = outside.read_text(encoding="utf-8")
    mark = "SECRET-TMP" if leaked == "SECRET-TMP" else leaked.splitlines()[0]

    local = BodyguardPoolManager(tmp_path / "local")
    local.initialize_pool()
    local_ok = (local.states_dir / "agent-bodyguard-alpha.json").is_file()

    assert (err, mark, local_ok) == ("refusing to follow a symlink", "SECRET-TMP", True)
