import pytest
from scripts.github_customer_contract import (
    translate_github_error, validate_action, sanitize_headers, ErrorCategory, CourierGitHubError
)

def test_translate_github_401():
    err = translate_github_error(401)
    assert err.category == ErrorCategory.NEEDS_YOU
    assert "revoked or missing" in err.message

def test_translate_github_403_permission():
    err = translate_github_error(403, "Resource not accessible by integration")
    assert err.category == ErrorCategory.PERMISSION_REQUIRED

def test_translate_github_403_rate_limit():
    err = translate_github_error(403, "Secondary rate limit exceeded")
    assert err.category == ErrorCategory.GITHUB_UNAVAILABLE

def test_translate_github_404():
    err = translate_github_error(404, "Not found")
    assert err.category == ErrorCategory.NEEDS_YOU
    assert "not found" in err.message

def test_translate_github_422_conflict():
    err = translate_github_error(422, "A pull request already exists")
    assert err.category == ErrorCategory.NEEDS_YOU
    assert "Conflict" in err.message

def test_translate_github_timeout_read():
    err = translate_github_error(0, is_timeout=True, is_mutation=False)
    assert err.category == ErrorCategory.RETRYING_SAFELY

def test_translate_github_timeout_mutation():
    err = translate_github_error(0, is_timeout=True, is_mutation=True)
    assert err.category == ErrorCategory.ACTION_MAY_HAVE_HAPPENED

def test_validate_action_allows_safe():
    validate_action("create_pr")
    validate_action("read_issue")

def test_validate_action_blocks_forbidden():
    with pytest.raises(CourierGitHubError) as exc:
        validate_action("force_push")
    assert exc.value.category == ErrorCategory.ACTION_NOT_AUTHORIZED
    
    with pytest.raises(CourierGitHubError) as exc:
        validate_action("delete_repo")
    assert exc.value.category == ErrorCategory.ACTION_NOT_AUTHORIZED

def test_sanitize_headers():
    raw = {
        "Authorization": "Bearer gh_real_token",
        "Accept": "application/vnd.github.v3+json",
        "x-github-token": "secret123"
    }
    safe = sanitize_headers(raw)
    assert safe["Authorization"] == "***"
    assert safe["x-github-token"] == "***"
    assert safe["Accept"] == "application/vnd.github.v3+json"

from scripts.github_customer_contract import analyze_event, check_connection

def test_analyze_event_duplicate():
    seen = {"event-1"}
    with pytest.raises(CourierGitHubError) as exc:
        analyze_event("event-1", 100, 90, seen)
    assert exc.value.category == ErrorCategory.RETRYING_SAFELY
    assert "Duplicate" in exc.value.message

def test_analyze_event_stale():
    seen = set()
    with pytest.raises(CourierGitHubError) as exc:
        analyze_event("event-2", 1000, 100, seen) # 900 seconds old
    assert exc.value.category == ErrorCategory.RETRYING_SAFELY
    assert "Stale" in exc.value.message

def test_check_connection_disconnected():
    with pytest.raises(CourierGitHubError) as exc:
        check_connection(False)
    assert exc.value.category == ErrorCategory.NEEDS_YOU
    assert "disconnected" in exc.value.message

def test_check_connection_connected():
    check_connection(True)

def test_translate_github_502_partial_api_failure():
    err = translate_github_error(502)
    assert err.category == ErrorCategory.GITHUB_UNAVAILABLE
    assert "down" in err.message.lower()

def test_translate_github_422_branch_deleted():
    err = translate_github_error(422, "Reference does not exist")
    assert err.category == ErrorCategory.NEEDS_YOU
    assert "conflict" in err.message.lower()

def test_translate_github_409_conflict():
    err = translate_github_error(409, "Merge conflict")
    assert err.category == ErrorCategory.NEEDS_YOU
    assert "conflict" in err.message.lower()

def test_user_disconnects_while_work_is_running():
    # If the token disappears mid-flight, it's equivalent to 401 or check_connection(False)
    with pytest.raises(CourierGitHubError) as exc:
        check_connection(False)
    assert exc.value.category == ErrorCategory.NEEDS_YOU
def test_translate_github_success():
    # Translating a success isn't typically an error, but in a mocked context, we can test that 200/201 doesn't raise, or just document it.
    # The adapter itself handles 200/201. We'll simulate a 200 check here.
    err = translate_github_error(200)
    assert err.category == ErrorCategory.RETRYING_SAFELY  # Fallback if an exception was forced

def test_translate_github_malformed_response():
    # Simulating a scenario where response is garbled
    err = translate_github_error(502, "Bad Gateway - HTML returned instead of JSON")
    assert err.category == ErrorCategory.GITHUB_UNAVAILABLE

def test_translate_429_rate_limit_retries_safely_never_fails_hard():
    # 429 has no dedicated branch; it must fall through to safe retry,
    # never to NEEDS_YOU / PERMISSION_REQUIRED / ACTION_NOT_AUTHORIZED.
    for message in ("", "API rate limit exceeded", "secondary rate limit"):
        err = translate_github_error(429, message)
        assert err.category == ErrorCategory.RETRYING_SAFELY
