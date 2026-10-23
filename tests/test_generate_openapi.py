import json
import runpy
from pathlib import Path


def test_openapi_does_not_follow_a_symlink(tmp_path, monkeypatch, capsys):
    script = Path(__file__).resolve().parents[1] / "scripts" / "generate_openapi.py"

    def run(root):
        monkeypatch.chdir(root)
        try:
            runpy.run_path(str(script), run_name="__main__")
            return None
        except ValueError as exc:
            return str(exc)

    out_root = tmp_path / "out-case"
    (out_root / "server").mkdir(parents=True)
    (out_root / "server" / "app.py").write_text(
        '@app.route("/health")\ndef health():\n    return "ok"\n',
        encoding="utf-8",
    )
    (out_root / "static").mkdir()
    outside = tmp_path / "outside-openapi.json"
    outside.write_text("SECRET-OPENAPI\n", encoding="utf-8")
    (out_root / "static" / "openapi.json").symlink_to(outside)
    out_err = run(out_root)
    out_body = outside.read_text(encoding="utf-8")

    src_root = tmp_path / "src-case"
    (src_root / "server").mkdir(parents=True)
    (src_root / "static").mkdir()
    secret_app = tmp_path / "secret-app.py"
    secret_app.write_text(
        '@app.route("/SECRET-ROUTE")\ndef secret():\n    return "no"\n',
        encoding="utf-8",
    )
    (src_root / "server" / "app.py").symlink_to(secret_app)
    src_err = run(src_root)
    spec = src_root / "static" / "openapi.json"
    spec_body = spec.read_text(encoding="utf-8") if spec.exists() else ""
    assert (
        out_err,
        "SECRET-OPENAPI" in out_body,
        "/health" in out_body,
        src_err,
        "SECRET-ROUTE" in spec_body,
        "SECRET-ROUTE" in secret_app.read_text(encoding="utf-8"),
    ) == (
        "refusing to follow a symlink",
        True,
        False,
        "refusing to follow a symlink",
        False,
        True,
    )


def test_openapi_writes_a_local_spec(tmp_path, monkeypatch, capsys):
    script = Path(__file__).resolve().parents[1] / "scripts" / "generate_openapi.py"
    monkeypatch.chdir(tmp_path)
    (tmp_path / "server").mkdir()
    (tmp_path / "static").mkdir()
    (tmp_path / "server" / "app.py").write_text(
        '@app.route("/health")\ndef health():\n    return "ok"\n',
        encoding="utf-8",
    )
    runpy.run_path(str(script), run_name="__main__")
    spec = json.loads((tmp_path / "static" / "openapi.json").read_text(encoding="utf-8"))
    assert "/health" in spec["paths"]
