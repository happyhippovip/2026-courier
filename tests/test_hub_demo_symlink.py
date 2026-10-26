import pytest

from courier_hub.demo import _controller_token, _spawn, main


def test_demo_refuses_a_symlinked_home(tmp_path):
    outside = tmp_path / "outside"
    (outside / "run").mkdir(parents=True)
    secret = "SECRET-TOKEN-VALUE-THAT-IS-LONG-ENOUGH"
    (outside / "run" / "controller.token").write_text(secret + "\n", encoding="utf-8")
    link = tmp_path / "home"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(SystemExit) as caught:
        main(["--home", str(link), "--hub-port", "0"])
    assert "symlink" in str(caught.value).lower()
    assert not (outside / "controller.log").exists()
    assert (outside / "run" / "controller.token").read_text(encoding="utf-8") == secret + "\n"

    real = tmp_path / "real"
    (real / "run").mkdir(parents=True)
    (real / "run" / "controller.token").write_text(secret + "\n", encoding="utf-8")
    assert _controller_token(real) == secret

    log_target = tmp_path / "log-target"
    log_target.write_bytes(b"SECRET")
    (real / "controller.log").symlink_to(log_target)
    with pytest.raises(SystemExit) as caught:
        _spawn(["courier_core.serve"], real, "controller.log")
    assert "symlink" in str(caught.value).lower()
    assert log_target.read_bytes() == b"SECRET"
