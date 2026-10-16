"""Pilot-site contracts: internal links, the not-found page, and the build."""
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
import pytest

from website.site_check import broken_internal_links, not_found_home_href, resolve_request

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "website" / "src"


def _stage(tmp_path):
    dest = tmp_path / "website"
    dest.mkdir()
    shutil.copy(ROOT / "website" / "build_site.sh", dest / "build_site.sh")
    shutil.copytree(SRC, dest / "src")
    os.chmod(dest / "build_site.sh", 0o755)
    return dest


def _build(dest, email=None):
    if sys.platform == "win32":
        pytest.skip("build_site.sh requires a UNIX shell")
    env = os.environ.copy()
    env.pop("COURIER_CONTACT_EMAIL", None)
    if email is not None:
        env["COURIER_CONTACT_EMAIL"] = email
    return subprocess.run(
        ["./build_site.sh"], cwd=dest, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30,
    )


def _tree_hash(directory):
    digest = hashlib.sha256()
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(directory)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_missing_relative_link_is_reported(tmp_path):
    page = tmp_path / "a.html"
    page.write_text('<a href="missing.html">x</a><a href="https://example.com">y</a>', encoding="utf-8")
    assert broken_internal_links(tmp_path) == [("a.html", "missing.html")]


def test_parent_escape_is_reported(tmp_path):
    page = tmp_path / "a.html"
    page.write_text('<a href="../outside.html">x</a>', encoding="utf-8")
    assert broken_internal_links(tmp_path) == [("a.html", "../outside.html")]


def test_src_internal_links_resolve():
    assert broken_internal_links(SRC) == []


def test_same_broken_set_on_second_read(tmp_path):
    page = tmp_path / "a.html"
    page.write_text('<a href="missing.html">x</a>', encoding="utf-8")
    assert broken_internal_links(tmp_path) == broken_internal_links(tmp_path)


def test_404_home_link_names_index():
    html = (SRC / "404.html").read_text(encoding="utf-8")
    assert not_found_home_href(html) == "index.html"
    assert 'href="/"' not in html


def test_unknown_path_is_404_and_index_is_not(tmp_path):
    (tmp_path / "index.html").write_text("<h1>home</h1>", encoding="utf-8")
    (tmp_path / "404.html").write_text("<h1>missing</h1>", encoding="utf-8")
    assert resolve_request(tmp_path, "/no-such") == "404"
    assert resolve_request(tmp_path, "/index.html") == "index.html"
    assert resolve_request(tmp_path, "/") == "index.html"
    assert resolve_request(tmp_path, "/../secret") == "404"
    assert resolve_request(tmp_path, "/404.html") == "404.html"


def test_resolve_request_is_stable(tmp_path):
    (tmp_path / "index.html").write_text("home", encoding="utf-8")
    assert resolve_request(tmp_path, "/missing") == resolve_request(tmp_path, "/missing")


def test_committed_public_html_matches_src():
    public = ROOT / "website" / "public"
    for page in SRC.glob("*.html"):
        assert (public / page.name).read_bytes() == page.read_bytes()


def test_build_without_email_matches_src_twice(tmp_path):
    dest = _stage(tmp_path)
    first = _build(dest)
    assert first.returncode == 0, first.stderr
    left = _tree_hash(dest / "public")
    second = _build(dest)
    assert second.returncode == 0, second.stderr
    assert _tree_hash(dest / "public") == left
    for page in (dest / "src").glob("*.html"):
        assert (dest / "public" / page.name).read_bytes() == page.read_bytes()


def test_build_inserts_a_simple_contact_email(tmp_path):
    dest = _stage(tmp_path)
    result = _build(dest, email="pilot@example.com")
    assert result.returncode == 0, result.stderr
    built = (dest / "public" / "index.html").read_text(encoding="utf-8")
    assert "oder pilot@example.com" in built
    assert '<a href="community.html">Community / Mitbauen</a>' in built
    assert "pilot@example.com" not in (dest / "src" / "index.html").read_text(encoding="utf-8")


def test_build_rejects_a_contact_email_that_can_break_the_script(tmp_path):
    dest = _stage(tmp_path)
    result = _build(dest, email="pilot@example.com; rm -rf /")
    assert result.returncode != 0
    built = dest / "public" / "index.html"
    if built.exists():
        assert "rm -rf" not in built.read_text(encoding="utf-8")
