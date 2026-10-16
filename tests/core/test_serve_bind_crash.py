import pytest
def test_service_init_bind_failure_closes_journal(tmp_path, monkeypatch):
    import courier_core.serve as s
    monkeypatch.setattr(s, "ControllerServer", lambda *a, **k: (_ for _ in ()).throw(OSError("bind")))
    with pytest.raises(OSError):
        s.Service(tmp_path, 0)
    (tmp_path / "courier.db").rename(tmp_path / "moved.db")
