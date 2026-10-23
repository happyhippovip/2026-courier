"""A symlink inside the hub static directory must not be served."""

from courier_hub import server


def test_static_symlink_is_not_served(tmp_path):
    outside = tmp_path / "secret.html"
    outside.write_text("SECRET", encoding="utf-8")
    link = server.STATIC_DIR / "zz-symlink-probe.html"
    link.symlink_to(outside)
    sent = {}

    class Fake:
        def _send(self, status, payload=None, content_type="application/json", raw=None):
            sent["status"] = status
            sent["raw"] = raw
            sent["payload"] = payload

    try:
        server.Handler._static(Fake(), "/zz-symlink-probe.html")
    finally:
        link.unlink(missing_ok=True)
    assert not link.exists()
    assert sent.get("status") == 404, sent
    assert sent.get("raw") != b"SECRET"
    assert outside.read_text(encoding="utf-8") == "SECRET"
    real = {}

    class Real:
        def _send(self, status, payload=None, content_type="application/json", raw=None):
            real["status"] = status
            real["raw"] = raw

    server.Handler._static(Real(), "/")
    assert real["status"] == 200
    assert real["raw"].startswith(b"<!DOCTYPE html>") or real["raw"].startswith(b"<!")
