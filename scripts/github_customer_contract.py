import enum

class ErrorCategory(enum.Enum):
    NEEDS_YOU = "NEEDS YOU"
    RETRYING_SAFELY = "RETRYING SAFELY"
    PERMISSION_REQUIRED = "PERMISSION REQUIRED"
    GITHUB_UNAVAILABLE = "GITHUB UNAVAILABLE"
    ACTION_NOT_AUTHORIZED = "ACTION NOT AUTHORIZED"
    ACTION_MAY_HAVE_HAPPENED = "ACTION MAY HAVE HAPPENED / VERIFY"

class CourierGitHubError(Exception):
    def __init__(self, category: ErrorCategory, message: str):
        super().__init__(f"{category.value}: {message}")
        self.category = category
        self.message = message

def translate_github_error(status_code: int, error_message: str = "", is_mutation: bool = False, is_timeout: bool = False) -> CourierGitHubError:
    if is_timeout:
        if is_mutation:
            return CourierGitHubError(ErrorCategory.ACTION_MAY_HAVE_HAPPENED, "Network timeout during modification.")
        return CourierGitHubError(ErrorCategory.RETRYING_SAFELY, "Network timeout.")

    if status_code == 401:
        return CourierGitHubError(ErrorCategory.NEEDS_YOU, "Authorization revoked or missing.")
    
    if status_code == 403:
        if "rate limit" in error_message.lower() or "secondary rate limit" in error_message.lower():
            return CourierGitHubError(ErrorCategory.GITHUB_UNAVAILABLE, "Rate limit exceeded.")
        return CourierGitHubError(ErrorCategory.PERMISSION_REQUIRED, "Insufficient repository permission.")
    
    if status_code == 404:
        return CourierGitHubError(ErrorCategory.NEEDS_YOU, "Repository or resource not found.")
        
    if status_code in (409, 422):
        if "already exists" in error_message.lower() or "protection" in error_message.lower():
            return CourierGitHubError(ErrorCategory.NEEDS_YOU, "Conflict or protection rule prevented action.")
        return CourierGitHubError(ErrorCategory.NEEDS_YOU, "API conflict or unprocessable entity.")
        
    if status_code >= 500:
        return CourierGitHubError(ErrorCategory.GITHUB_UNAVAILABLE, "GitHub API is currently down.")
        
    return CourierGitHubError(ErrorCategory.RETRYING_SAFELY, "Transient or unknown failure.")

def validate_action(action_type: str) -> None:
    forbidden = {"delete_repo", "force_push", "admin", "read_secrets"}
    if action_type in forbidden:
        raise CourierGitHubError(ErrorCategory.ACTION_NOT_AUTHORIZED, f"Action {action_type} is not permitted by Courier.")

def sanitize_headers(headers: dict) -> dict:
    safe_headers = headers.copy()
    for sensitive in ("authorization", "x-github-token", "bearer"):
        for k in list(safe_headers.keys()):
            if k.lower() == sensitive:
                safe_headers[k] = "***"
    return safe_headers


def analyze_event(event_id: str, current_time: float, event_timestamp: float, seen_events: set) -> None:
    if event_id in seen_events:
        raise CourierGitHubError(ErrorCategory.RETRYING_SAFELY, "Duplicate event received.")
    if current_time - event_timestamp > 300: # 5 minutes
        raise CourierGitHubError(ErrorCategory.RETRYING_SAFELY, "Stale event ignored.")
    seen_events.add(event_id)

def check_connection(is_connected: bool) -> None:
    if not is_connected:
        raise CourierGitHubError(ErrorCategory.NEEDS_YOU, "User disconnected while work is running.")
