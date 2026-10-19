"""OAuth 2.1 (PKCE) for the read-only Courier MCP server."""

import hashlib
import json
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest

from courier_mcp import oauth as oauth_mod
from courier_mcp import server as srv
from courier_mcp.oauth import FIXED_CLIENT_ID, SCOPE, OAuthServer, s256

PASSWORD = "p" * 40
PUBLIC = "https://demo.example"


def _clock(start=1_700_000_000.0):
    state = {"t": start}

    def now():
        return state["t"]

    now.advance = lambda seconds: state.__setitem__("t", state["t"] + seconds)
    return now


@pytest.fixture()
def oauth(tmp_path):
    clock = _clock()
    server = OAuthServer(PUBLIC, PASSWORD, tmp_path / "oauth_store.json", clock=clock, log=lambda *_: None)
    return server, clock


def _challenge():
    verifier = secrets.token_urlsafe(48)
    return verifier, s256(verifier)


def test_metadata_contents(oauth):
    server, _ = oauth
    as_meta = server.authorization_server_metadata()
    assert as_meta["issuer"] == PUBLIC
    assert as_meta["authorization_endpoint"] == PUBLIC + "/authorize"
    assert as_meta["token_endpoint"] == PUBLIC + "/token"
    assert as_meta["registration_endpoint"] == PUBLIC + "/register"
    assert as_meta["code_challenge_methods_supported"] == ["S256"]
    assert as_meta["token_endpoint_auth_methods_supported"] == ["none"]
    assert as_meta["scopes_supported"] == [SCOPE]
    pr = server.protected_resource_metadata()
    assert pr["resource"] == PUBLIC + "/mcp"
    assert pr["authorization_servers"] == [PUBLIC]
    assert 'resource_metadata="' + PUBLIC + '/.well-known/oauth-protected-resource"' in server.www_authenticate()


def test_redirect_uri_allowlist():
    assert oauth_mod.redirect_allowed("https://grok.com/callback")
    assert oauth_mod.redirect_allowed("https://app.x.ai/oauth")
    assert not oauth_mod.redirect_allowed("http://grok.com/callback")
    assert not oauth_mod.redirect_allowed("https://evil.com/?https://grok.com")
    assert not oauth_mod.redirect_allowed("https://grok.com.evil.com/")
    assert not oauth_mod.redirect_allowed("https://user@grok.com/")


def test_full_pkce_flow(oauth):
    server, _ = oauth
    verifier, challenge = _challenge()
    request = server.check_authorize({
        "response_type": "code", "client_id": FIXED_CLIENT_ID,
        "redirect_uri": "https://grok.com/cb", "code_challenge": challenge,
        "code_challenge_method": "S256", "state": "abc", "scope": SCOPE,
    })
    location = server.approve(request, PASSWORD)
    code = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)["code"][0]
    assert "state=abc" in location
    tokens = server.token({
        "grant_type": "authorization_code", "code": code, "redirect_uri": "https://grok.com/cb",
        "client_id": FIXED_CLIENT_ID, "code_verifier": verifier,
    })
    assert tokens["token_type"] == "Bearer" and tokens["scope"] == SCOPE and tokens["expires_in"] == 3600
    assert server.access_ok(tokens["access_token"]) is True
    assert server.access_ok("not-a-token") is False
    store = json.loads((server._store_path).read_text())
    assert hashlib.sha256(tokens["access_token"].encode()).hexdigest() in store["access"]
    assert tokens["access_token"] not in json.dumps(store)


def test_wrong_verifier_and_code_reuse(oauth):
    server, _ = oauth
    verifier, challenge = _challenge()
    request = server.check_authorize({
        "response_type": "code", "client_id": FIXED_CLIENT_ID, "redirect_uri": "https://grok.com/cb",
        "code_challenge": challenge, "code_challenge_method": "S256",
    })
    location = server.approve(request, PASSWORD)
    code = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)["code"][0]
    with pytest.raises(oauth_mod.OAuthError) as exc:
        server.token({"grant_type": "authorization_code", "code": code, "redirect_uri": "https://grok.com/cb",
                      "client_id": FIXED_CLIENT_ID, "code_verifier": secrets.token_urlsafe(48)})
    assert exc.value.error == "invalid_grant"
    # code is spent even on PKCE failure
    with pytest.raises(oauth_mod.OAuthError) as exc:
        server.token({"grant_type": "authorization_code", "code": code, "redirect_uri": "https://grok.com/cb",
                      "client_id": FIXED_CLIENT_ID, "code_verifier": verifier})
    assert exc.value.error == "invalid_grant"


def test_bad_redirect_uri(oauth):
    server, logs = oauth[0], []
    server._log = logs.append
    with pytest.raises(oauth_mod.OAuthError):
        server.check_authorize({
            "response_type": "code", "client_id": FIXED_CLIENT_ID,
            "redirect_uri": "https://evil.example/cb", "code_challenge": s256("a" * 43),
            "code_challenge_method": "S256",
        })
    assert any("host=evil.example" in line for line in logs)
    with pytest.raises(oauth_mod.OAuthError) as exc:
        server.register({"redirect_uris": ["https://not-allowed.test/cb"]})
    assert exc.value.error == "invalid_redirect_uri"


def test_expired_code(oauth):
    server, clock = oauth
    verifier, challenge = _challenge()
    request = server.check_authorize({
        "response_type": "code", "client_id": FIXED_CLIENT_ID, "redirect_uri": "https://x.ai/r",
        "code_challenge": challenge, "code_challenge_method": "S256",
    })
    location = server.approve(request, PASSWORD)
    code = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)["code"][0]
    clock.advance(121)
    with pytest.raises(oauth_mod.OAuthError) as exc:
        server.token({"grant_type": "authorization_code", "code": code, "redirect_uri": "https://x.ai/r",
                      "client_id": FIXED_CLIENT_ID, "code_verifier": verifier})
    assert exc.value.error == "invalid_grant"


def test_wrong_approval_password_rate_limit(oauth):
    server, clock = oauth
    request = server.check_authorize({
        "response_type": "code", "client_id": FIXED_CLIENT_ID, "redirect_uri": "https://grok.com/cb",
        "code_challenge": s256("v" * 43), "code_challenge_method": "S256",
    })
    for _ in range(5):
        with pytest.raises(oauth_mod.OAuthError) as exc:
            server.approve(request, "wrong")
        assert exc.value.error == "wrong_password"
    with pytest.raises(oauth_mod.OAuthError) as exc:
        server.approve(request, PASSWORD)
    assert exc.value.error == "locked" and exc.value.status == 429
    clock.advance(601)
    location = server.approve(request, PASSWORD)
    assert "code=" in location


def test_refresh_rotates(oauth):
    server, clock = oauth
    verifier, challenge = _challenge()
    request = server.check_authorize({
        "response_type": "code", "client_id": FIXED_CLIENT_ID, "redirect_uri": "https://grok.com/cb",
        "code_challenge": challenge, "code_challenge_method": "S256",
    })
    code = urllib.parse.parse_qs(urllib.parse.urlparse(server.approve(request, PASSWORD)).query)["code"][0]
    first = server.token({"grant_type": "authorization_code", "code": code, "redirect_uri": "https://grok.com/cb",
                          "client_id": FIXED_CLIENT_ID, "code_verifier": verifier})
    second = server.token({"grant_type": "refresh_token", "refresh_token": first["refresh_token"],
                           "client_id": FIXED_CLIENT_ID})
    assert second["access_token"] != first["access_token"]
    with pytest.raises(oauth_mod.OAuthError):
        server.token({"grant_type": "refresh_token", "refresh_token": first["refresh_token"],
                      "client_id": FIXED_CLIENT_ID})
    clock.advance(3601)
    assert server.access_ok(second["access_token"]) is False


def test_dynamic_registration(oauth):
    server, _ = oauth
    registered = server.register({"redirect_uris": ["https://app.grok.com/oauth"], "client_name": "Grok"})
    assert registered["client_id"].startswith("dcr-")
    assert registered["token_endpoint_auth_method"] == "none"
    verifier, challenge = _challenge()
    request = server.check_authorize({
        "response_type": "code", "client_id": registered["client_id"],
        "redirect_uri": "https://app.grok.com/oauth", "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    assert request["client_id"] == registered["client_id"]


# ---- over HTTP --------------------------------------------------------------

TOKEN = "t" * 40


@pytest.fixture()
def running_oauth(tmp_path):
    started = []

    def start():
        store = tmp_path / "store.json"
        config = srv.build_config(
            srv.parse_args(["--demo", "--allow-path-token", "--oauth",
                            "--public-url", "https://demo.example",
                            "--oauth-store", str(store)]),
            {"COURIER_MCP_TOKEN": TOKEN},
        )
        server = srv.make_server(config, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        started.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield start
    for server in started:
        server.shutdown()
        server.server_close()


def _get(url, follow=False):
    request = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def _post_form(url, form, headers=None):
    data = urllib.parse.urlencode(form).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return (exc.code, exc.read(), dict(exc.headers))


def test_http_pkce_and_mcp_with_access_token(running_oauth):
    base = running_oauth()
    status, body, _ = _get(base + "/.well-known/oauth-authorization-server")
    assert status == 200 and json.loads(body)["issuer"] == "https://demo.example"
    status, body, headers = _get(base + "/.well-known/oauth-protected-resource")
    assert json.loads(body)["resource"] == "https://demo.example/mcp"
    verifier, challenge = _challenge()
    query = urllib.parse.urlencode({
        "response_type": "code", "client_id": FIXED_CLIENT_ID,
        "redirect_uri": "https://grok.com/cb", "code_challenge": challenge,
        "code_challenge_method": "S256", "state": "s1", "scope": SCOPE,
    })
    status, body, _ = _get(base + "/authorize?" + query)
    assert status == 200 and b"Freigabe-Passwort" in body and b"courier-grok" in body
    # wrong password
    status, body, _ = _post_form(base + "/authorize", {
        "response_type": "code", "client_id": FIXED_CLIENT_ID, "redirect_uri": "https://grok.com/cb",
        "code_challenge": challenge, "code_challenge_method": "S256", "state": "s1", "scope": SCOPE,
        "password": "wrong", "decision": "allow",
    })
    assert status == 401 and b"Falsches Passwort" in body
    # approve
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(NoRedirect)
    data = urllib.parse.urlencode({
        "response_type": "code", "client_id": FIXED_CLIENT_ID, "redirect_uri": "https://grok.com/cb",
        "code_challenge": challenge, "code_challenge_method": "S256", "state": "s1", "scope": SCOPE,
        "password": TOKEN, "decision": "allow",
    }).encode()
    request = urllib.request.Request(base + "/authorize", data=data, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        opener.open(request, timeout=10)
        raise AssertionError("expected 302")
    except urllib.error.HTTPError as exc:
        assert exc.code == 302
        location = exc.headers["Location"]
    parsed = urllib.parse.urlparse(location)
    assert parsed.scheme == "https" and parsed.hostname == "grok.com"
    code = urllib.parse.parse_qs(parsed.query)["code"][0]
    status, body, _ = _post_form(base + "/token", {
        "grant_type": "authorization_code", "code": code, "redirect_uri": "https://grok.com/cb",
        "client_id": FIXED_CLIENT_ID, "code_verifier": verifier,
    })
    tokens = json.loads(body)
    assert status == 200 and tokens["access_token"]
    # MCP with access token
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).encode()
    request = urllib.request.Request(base + "/mcp", data=payload, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", "Bearer " + tokens["access_token"])
    with urllib.request.urlopen(request, timeout=10) as response:
        listed = json.loads(response.read())
    assert len(listed["result"]["tools"]) == 6
    # 401 advertises protected-resource metadata
    request = urllib.request.Request(base + "/mcp", data=payload, method="POST")
    request.add_header("Content-Type", "application/json")
    try:
        urllib.request.urlopen(request, timeout=10)
        raise AssertionError
    except urllib.error.HTTPError as exc:
        assert exc.code == 401
        assert "oauth-protected-resource" in exc.headers["WWW-Authenticate"]


def test_static_bearer_still_works_with_oauth(running_oauth):
    base = running_oauth()
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}).encode()
    request = urllib.request.Request(base + "/mcp", data=payload, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", "Bearer " + TOKEN)
    with urllib.request.urlopen(request, timeout=10) as response:
        assert json.loads(response.read())["result"] == {}


def test_consent_form_roundtrip_with_resource(running_oauth):
    base = running_oauth()
    verifier, challenge = _challenge()
    query = urllib.parse.urlencode({
        "response_type": "code", "client_id": FIXED_CLIENT_ID, "redirect_uri": "https://grok.com/cb",
        "code_challenge": challenge, "code_challenge_method": "S256",
        "resource": "https://demo.example/mcp",
    })
    status, body, headers = _get(base + "/authorize?" + query)
    assert status == 200 and headers["X-Frame-Options"] == "DENY"
    # the form posts every hidden field back, including empty state/resource
    status, body, _ = _post_form(base + "/authorize", {
        "response_type": "code", "client_id": FIXED_CLIENT_ID, "redirect_uri": "https://grok.com/cb",
        "code_challenge": challenge, "code_challenge_method": "S256", "state": "", "scope": SCOPE,
        "resource": "", "password": "nope", "decision": "allow",
    })
    assert status == 401


def test_bad_redirect_over_http_is_not_redirected(running_oauth):
    base = running_oauth()
    query = urllib.parse.urlencode({
        "response_type": "code", "client_id": FIXED_CLIENT_ID, "redirect_uri": "https://evil.example/cb",
        "code_challenge": s256("v" * 43), "code_challenge_method": "S256",
    })
    status, body, headers = _get(base + "/authorize?" + query)
    assert status == 400 and "Location" not in headers


def test_oauth_config_refusals(tmp_path):
    env = {"COURIER_MCP_TOKEN": TOKEN}
    with pytest.raises(srv.ConfigError):
        srv.build_config(srv.parse_args(["--demo", "--oauth"]), env)
    with pytest.raises(srv.ConfigError):
        srv.build_config(srv.parse_args(["--demo", "--oauth", "--public-url", "http://plain.example",
                                         "--oauth-store", str(tmp_path / "s.json")]), env)
    with pytest.raises(srv.ConfigError):
        srv.build_config(srv.parse_args(["--demo", "--oauth", "--public-url", "https://ok.example",
                                         "--oauth-store", str(tmp_path / "s.json")]), {})
