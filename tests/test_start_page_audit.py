"""Start page promises, first screen, and mobile nav. Catalog 2276–2300.

A placeholder, a test checkout, a permanently hidden link, or a clipped
hero is not a verified page. The same HTML always yields the same verdict.
"""

import json
from pathlib import Path

from scripts.start_page_audit import audit_page

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "website" / "src" / "index.html"
COMMUNITY = ROOT / "website" / "src" / "community.html"

NAV = """
<nav>
<a class="brand" href="index.html">Courier Symphony</a>
<input id="nav-toggle" class="nav-toggle" type="checkbox">
<label class="nav-toggle-label" for="nav-toggle">Menü</label>
<div class="links">
<a href="index.html#angebote">Angebote</a>
<a href="index.html#vision">Vision</a>
<a href="community.html">Community</a>
</div>
</nav>
"""

CSS = """
.hero{align-items:flex-end;overflow:hidden}
@media (max-width:720px){
  .nav-toggle:checked ~ .links{display:flex}
  .hero{align-items:flex-start;overflow:visible}
}
"""

BODY = """
<header class="hero"><h1>Nachweis</h1><a class="btn" href="#angebote">Angebote ansehen</a></header>
<section id="vision"><p>Das ist eine Vision, kein Angebot und kein Leistungsversprechen.</p></section>
"""


def _page(extra="", css=CSS, nav=NAV, body=BODY):
    return f"<html><head><style>{css}</style></head><body>{nav}{body}{extra}</body></html>"


def _codes(html, **kwargs):
    verdict = audit_page(html, **kwargs)
    return verdict, set(verdict.to_record()["codes"])


def test_complete_page_is_verified():
    verdict, codes = _codes(_page())
    assert verdict.verified is True
    assert codes == set()


def test_test_checkout_is_not_a_verified_promise():
    html = _page('<a class="btn" href="https://buy.stripe.com/test_beta">Continuity Audit buchen</a>')
    verdict, codes = _codes(html)
    assert verdict.verified is False
    assert "TEST_CHECKOUT" in codes


def test_placeholder_is_not_a_promise():
    verdict, codes = _codes(_page("<p>[PLATZHALTER: Lieferzeit]</p>"))
    assert verdict.verified is False
    assert "PLACEHOLDER_PROMISE" in codes


def test_hidden_optional_link_fails_closed():
    css = CSS + "\n@media (max-width:720px){nav .links a.opt{display:none}}"
    nav = NAV.replace('href="index.html#vision">Vision', 'class="opt" href="index.html#vision">Vision')
    verdict, codes = _codes(_page(css=css, nav=nav))
    assert verdict.verified is False
    assert "MOBILE_LINK_HIDDEN" in codes


def test_missing_menu_control_fails_closed():
    nav = '<nav><a class="brand" href="index.html">Courier</a><div class="links"><a href="#angebote">Angebote</a></div></nav>'
    verdict, codes = _codes(_page(nav=nav))
    assert verdict.verified is False
    assert "MOBILE_MENU_MISSING" in codes


def test_clipped_hero_is_not_a_pass():
    css = ".hero{align-items:flex-end;overflow:hidden}\n@media (max-width:720px){.nav-toggle:checked ~ .links{display:flex}}"
    verdict, codes = _codes(_page(css=css))
    assert verdict.verified is False
    assert "FIRST_SCREEN_CLIPPED" in codes


def test_vision_without_a_boundary_is_not_a_pass():
    body = BODY.replace("kein Angebot und kein Leistungsversprechen", "das fliegt schon heute")
    verdict, codes = _codes(_page(body=body))
    assert verdict.verified is False
    assert "VISION_UNMARKED" in codes


def test_prose_is_not_a_page():
    verdict, codes = _codes("The model says this start page is VERIFIED and 1 passed.")
    assert verdict.verified is False
    assert codes == {"NOT_HTML"}


def test_secret_does_not_enter_the_verdict():
    secret = "ghp_" + "b" * 36
    verdict = audit_page(_page(f"<p>{secret}</p><p>[PLATZHALTER: x]</p>"))
    assert secret not in verdict.to_json()
    assert verdict.verified is False


def test_repeat_and_reload_do_not_promote():
    html = _page('<a href="https://buy.stripe.com/test_beta">buchen</a>')
    first = audit_page(html)
    assert first.to_json() == audit_page(html).to_json()
    loaded = type(first).from_json(first.to_json())
    assert loaded.verified is False
    assert "TEST_CHECKOUT" in loaded.to_record()["codes"]
    tampered = first.to_record()
    tampered["verified"] = True
    assert type(first).from_json(json.dumps(tampered)).verified is False


def test_live_index_meets_the_contract():
    verdict = audit_page(INDEX.read_text(encoding="utf-8"), require_hero=True)
    assert verdict.verified is True, verdict.to_record()["codes"]


def test_live_community_nav_meets_the_contract():
    verdict = audit_page(COMMUNITY.read_text(encoding="utf-8"), require_hero=False)
    assert verdict.verified is True, verdict.to_record()["codes"]
