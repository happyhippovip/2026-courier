"""Pull one page of GitHub inbox comments and turn a verified wake into one task.

One invocation, no loop and no sleep. GitHub is read outbound. The controller
is local (127.0.0.1). The token is read from <home>/run/controller.token and
is never printed.

    python scripts/github_wake_inbox.py --repo owner/name --inbox-issue N \
        --courier-home DIR --allow-login owner
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MAX_PAGE = 50
MAX_WAKES = 5
MAX_BODY = 1_000_000
HTTP_TIMEOUT_S = 10.0
EXIT_MALFORMED = 2
EXIT_RETRY = 75
SCHEMA = "courier.wake.v1"
BASE_REF = "integration/v1"
BAD_CONCLUSIONS = frozenset({"failure", "cancelled", "timed_out"})
TASK_FIELDS = ("adapter", "params", "effect_class", "max_attempts", "lease_ttl_s", "timeout_s")
# serve.py --port defaults to 0 (ephemeral). Local clients use this host:port.
DEFAULT_CONTROLLER = "http://127.0.0.1:8080"


class Malformed(Exception):
    """Local cursor or parked-workkey state cannot be trusted."""


class ControllerDown(Exception):
    """The local controller could not be reached. The cursor stays put."""


class GitHubUnavailable(Exception):
    """GitHub could not be read. The cursor stays put."""


def main(argv=None, *, http=None, stdout=None, stderr=None) -> int:
    parser = argparse.ArgumentParser(description="One-shot GitHub comment to Courier task wake")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--inbox-issue", required=True, type=int)
    parser.add_argument("--courier-home", required=True)
    parser.add_argument("--controller", default=DEFAULT_CONTROLLER)
    parser.add_argument("--allow-login", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-wakes", type=int, default=MAX_WAKES)
    parser.add_argument("--timeout", type=float, default=HTTP_TIMEOUT_S)
    args = parser.parse_args(argv)
    say_out = stdout or (lambda line: print(line, flush=True))
    say_err = stderr or (lambda line: print(line, file=__import__("sys").stderr, flush=True))
    if not args.allow_login or args.max_wakes < 1 or args.timeout <= 0 or args.inbox_issue < 1:
        say_err("invalid arguments")
        return EXIT_MALFORMED
    if not _repo_ok(args.repo) or not _loopback(args.controller):
        say_err("repo must be owner/name and the controller must be loopback")
        return EXIT_MALFORMED
    home = Path(args.courier_home)
    try:
        cursor = _load_cursor(home / "run" / "github_wake.cursor")
        parked = _load_parked(home / "parked_workkeys.json")
    except Malformed:
        say_err("malformed local wake state")
        return EXIT_MALFORMED
    token = _read_token(home / "run" / "controller.token")
    github_token = os.environ.get("GITHUB_TOKEN") or ""
    secrets = [item for item in (token, github_token) if item]
    transport = http or _urllib_http

    def emit(record):
        line = json.dumps(record, sort_keys=True, separators=(",", ":"))
        say_out(_redact(line, secrets))
        if not args.dry_run:
            _append(home / "run" / "github_wake.log", line + "\n")

    try:
        comments = _comments(transport, args, cursor, github_token)
    except GitHubUnavailable:
        say_err(_redact("github comment page unavailable", secrets))
        return 1
    handled = 0
    for comment in comments:
        if handled >= args.max_wakes:
            break
        cid = comment.get("id")
        if not isinstance(cid, int) or isinstance(cid, bool) or cid <= cursor["comment_id"]:
            continue
        outcome = _classify(comment, args.allow_login, args.repo)
        if outcome is None:
            emit({"comment_id": cid, "outcome": "ignored"})
            _advance(home, args, cursor, comment)
            continue
        handled += 1
        try:
            record = _decide(outcome, parked, args, transport, token, github_token)
        except ControllerDown:
            say_err(_redact("controller unreachable", secrets))
            return EXIT_RETRY
        except GitHubUnavailable:
            say_err(_redact("github verification unavailable", secrets))
            return 1
        emit(record)
        if not args.dry_run:
            _advance(home, args, cursor, comment)
    return 0


def _decide(wake, parked, args, transport, token, github_token):
    if not _event_verified(transport, args, wake, github_token):
        return {"wake_id": wake["wake_id"], "workkey": wake["workkey"], "outcome": "unverified"}
    entry = parked.get(wake["workkey"])
    if entry is None:
        return {"wake_id": wake["wake_id"], "workkey": wake["workkey"], "outcome": "ignored"}
    if not _dependencies_satisfied(transport, args, entry["depends_on"], github_token):
        return {"wake_id": wake["wake_id"], "workkey": wake["workkey"], "outcome": "not_satisfied"}
    if args.dry_run:
        return {"wake_id": wake["wake_id"], "workkey": wake["workkey"], "outcome": "queued"}
    if not token:
        raise ControllerDown()
    posted = _post_task(transport, args, token, wake["workkey"], entry)
    if posted.get("rejected"):
        return {"wake_id": wake["wake_id"], "workkey": wake["workkey"], "outcome": "unverified"}
    outcome = "duplicate" if posted.get("duplicate") is True else "queued"
    return {"wake_id": wake["wake_id"], "workkey": wake["workkey"], "outcome": outcome}


def _classify(comment, allow, repo):
    user = comment.get("user") if isinstance(comment, dict) else None
    login = user.get("login") if isinstance(user, dict) else None
    if login not in allow or comment.get("author_association") != "OWNER":
        return None
    fences = _fences(comment.get("body") if isinstance(comment.get("body"), str) else "")
    if len(fences) != 1:
        return None
    try:
        payload = json.loads(fences[0])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema") != SCHEMA or payload.get("repo") != repo:
        return None
    event = payload.get("event")
    if event not in ("pr_merged", "ci_passed"):
        return None
    wake_id = payload.get("wake_id")
    workkey = payload.get("workkey")
    sha = payload.get("sha")
    if not all(isinstance(item, str) and item for item in (wake_id, workkey, sha)):
        return None
    if not _sha_ok(sha):
        return None
    pr = payload.get("pr")
    if event == "pr_merged" and (isinstance(pr, bool) or not isinstance(pr, int) or pr < 1):
        return None
    if event == "ci_passed" and pr is not None and (isinstance(pr, bool) or not isinstance(pr, int)):
        return None
    return {"wake_id": wake_id, "workkey": workkey, "event": event, "sha": sha.lower(), "pr": pr, "repo": repo}


def _event_verified(transport, args, wake, github_token):
    if wake["event"] == "pr_merged":
        return _pull_ok(transport, args, wake["repo"], wake["pr"], wake["sha"], github_token)
    return _checks_ok(transport, args, wake["repo"], wake["sha"], github_token)


def _dependencies_satisfied(transport, args, deps, github_token):
    for dep in deps:
        repo = dep["repo"]
        if "pr" in dep:
            sha = dep.get("sha")
            sha = sha.lower() if isinstance(sha, str) else None
            if not _pull_ok(transport, args, repo, dep["pr"], sha, github_token):
                return False
        elif not _checks_ok(transport, args, repo, str(dep["sha"]).lower(), github_token):
            return False
    return True


def _pull_ok(transport, args, repo, number, sha, github_token):
    status, raw = _github(transport, args, f"/repos/{repo}/pulls/{number}", github_token)
    if not _github_readable(status):
        return False
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        return False
    base = body.get("base") if isinstance(body, dict) else None
    merged_sha = body.get("merge_commit_sha") if isinstance(body, dict) else None
    if not isinstance(body, dict) or body.get("merged") is not True:
        return False
    if not isinstance(base, dict) or base.get("ref") != BASE_REF:
        return False
    if not isinstance(merged_sha, str) or not _sha_ok(merged_sha):
        return False
    if sha is not None and merged_sha.lower() != sha.lower():
        return False
    return True


def _checks_ok(transport, args, repo, sha, github_token):
    status, raw = _github(
        transport, args, f"/repos/{repo}/commits/{sha}/check-runs?per_page={MAX_PAGE}&page=1", github_token,
    )
    if not _github_readable(status):
        return False
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        return False
    runs = body.get("check_runs") if isinstance(body, dict) else None
    total = body.get("total_count") if isinstance(body, dict) else None
    if not isinstance(runs, list) or not isinstance(total, int) or isinstance(total, bool):
        return False
    if total < 1 or total != len(runs) or len(runs) > MAX_PAGE:
        return False
    for run in runs:
        if not isinstance(run, dict) or run.get("status") != "completed":
            return False
        if run.get("conclusion") in BAD_CONCLUSIONS:
            return False
    return True


def _post_task(transport, args, token, workkey, entry):
    task = {name: entry["task"][name] for name in TASK_FIELDS if name in entry["task"]}
    task["idempotency_key"] = _idempotency(workkey, entry["depends_on"])
    url = args.controller.rstrip("/") + "/v1/tasks"
    try:
        status, raw = transport(
            "POST", url, {"X-Courier-Token": token, "Accept": "application/json", "Content-Type": "application/json"},
            json.dumps(task, sort_keys=True).encode("utf-8"), args.timeout,
        )
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        raise ControllerDown() from exc
    if status >= 500 or status == 0:
        raise ControllerDown()
    try:
        body = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        body = {}
    if status not in (200, 201) or not isinstance(body, dict):
        return {"duplicate": False, "rejected": True}
    return body


def _comments(transport, args, cursor, github_token):
    query = {"per_page": MAX_PAGE, "page": 1}
    if cursor.get("updated_at"):
        query["since"] = cursor["updated_at"]
    path = f"/repos/{args.repo}/issues/{args.inbox_issue}/comments?{urllib.parse.urlencode(query)}"
    status, raw = _github(transport, args, path, github_token)
    if status != 200:
        raise GitHubUnavailable()
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GitHubUnavailable() from exc
    if not isinstance(body, list) or len(body) > MAX_PAGE:
        raise GitHubUnavailable()
    return sorted((item for item in body if isinstance(item, dict)), key=lambda item: item.get("id") or 0)


def _github(transport, args, path, github_token):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "courier-wake-inbox"}
    if github_token:
        headers["Authorization"] = "Bearer " + github_token
    url = "https://api.github.com" + path
    try:
        status, raw = transport("GET", url, headers, None, args.timeout)
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        raise GitHubUnavailable() from exc
    if isinstance(raw, (bytes, bytearray)) and len(raw) > MAX_BODY:
        raise GitHubUnavailable()
    return status, raw


def _github_readable(status):
    """200 is readable. 404/422 are a definitive miss. Anything else is a retry."""
    if status == 200:
        return True
    if status in (404, 422):
        return False
    raise GitHubUnavailable()


def _idempotency(workkey, deps):
    rows = []
    for dep in deps:
        rows.append({"pr": dep.get("pr"), "repo": dep.get("repo"), "sha": dep.get("sha")})
    rows.sort(key=lambda row: (str(row["repo"]), str(row["pr"]), str(row["sha"])))
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"wake:{workkey}:{digest}"


def _advance(home, args, cursor, comment):
    updated = comment.get("updated_at") if isinstance(comment.get("updated_at"), str) else cursor.get("updated_at")
    nxt = {"comment_id": comment["id"], "updated_at": updated}
    _atomic_write(home / "run" / "github_wake.cursor", json.dumps(nxt, sort_keys=True) + "\n")
    cursor.update(nxt)


def _load_cursor(path: Path):
    if not path.exists():
        return {"comment_id": 0, "updated_at": None}
    data = _read_json(path)
    if not isinstance(data, dict):
        raise Malformed()
    cid = data.get("comment_id", 0)
    if isinstance(cid, bool) or not isinstance(cid, int) or cid < 0:
        raise Malformed()
    updated = data.get("updated_at")
    if updated is not None and not isinstance(updated, str):
        raise Malformed()
    return {"comment_id": cid, "updated_at": updated}


def _load_parked(path: Path):
    if not path.exists():
        return {}
    data = _read_json(path)
    if not isinstance(data, dict):
        raise Malformed()
    for key, value in data.items():
        if not isinstance(key, str) or not key or not isinstance(value, dict):
            raise Malformed()
        deps = value.get("depends_on")
        task = value.get("task")
        if not isinstance(deps, list) or not isinstance(task, dict):
            raise Malformed()
        for dep in deps:
            if not isinstance(dep, dict) or not _repo_ok(dep.get("repo")):
                raise Malformed()
            has_pr = "pr" in dep and not isinstance(dep["pr"], bool) and isinstance(dep["pr"], int) and dep["pr"] > 0
            has_sha = isinstance(dep.get("sha"), str) and _sha_ok(dep["sha"])
            if not has_pr and not has_sha:
                raise Malformed()
    return data


def _read_json(path: Path):
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise Malformed() from exc
    if len(raw) > MAX_BODY:
        raise Malformed()
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Malformed() from exc


def _read_token(path: Path):
    try:
        token = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""
    if len(token) < 32 or "\n" in token:
        return ""
    return token


def _fences(body: str):
    chunks = []
    marker = "```courier-wake"
    start = 0
    while True:
        at = body.find(marker, start)
        if at < 0:
            break
        line_end = body.find("\n", at)
        if line_end < 0:
            break
        close = body.find("\n```", line_end + 1)
        if close < 0:
            break
        chunks.append(body[line_end + 1:close])
        start = close + 4
    return chunks


def _repo_ok(repo):
    if not isinstance(repo, str) or repo.count("/") != 1:
        return False
    owner, name = repo.split("/")
    return bool(owner) and bool(name) and ".." not in repo and " " not in repo


def _sha_ok(sha):
    return isinstance(sha, str) and len(sha) == 40 and all(ch in "0123456789abcdefABCDEF" for ch in sha)


def _loopback(url):
    parsed = urllib.parse.urlsplit(url)
    return parsed.scheme in ("http", "https") and parsed.hostname in ("127.0.0.1", "localhost", "::1")


def _atomic_write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def _append(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()


def _redact(text, secrets):
    for secret in secrets:
        text = text.replace(secret, "[redacted]")
    return text


def _urllib_http(method, url, headers, body, timeout):
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_BODY + 1)
            if len(raw) > MAX_BODY:
                raise OSError("response too large")
            return response.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read(MAX_BODY + 1)
        return exc.code, raw[:MAX_BODY]


if __name__ == "__main__":
    import sys
    sys.exit(main())
