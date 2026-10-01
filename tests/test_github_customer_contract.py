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
