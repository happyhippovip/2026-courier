"""GitHub wake inbox. Injected HTTP only; no network and no controller process."""

import json

from scripts.github_wake_inbox import main

TOKEN = "controller-token-value-0123456789abcdef"
REPO = "acme/widgets"
SHA = "a" * 40
SHA2 = "b" * 40


def _comment(cid, login, association, payload, updated="2026-10-08T04:00:00Z"):
    body = "```courier-wake\n" + json.dumps(payload) + "\n```"
    return {
        "id": cid,
        "user": {"login": login},
        "author_association": association,
        "body": body,
        "updated_at": updated,
    }


def _wake(event="pr_merged", pr=7, sha=SHA, workkey="wk-a", wake_id="w-a"):
    body = {
        "schema": "courier.wake.v1",
        "wake_id": wake_id,
        "repo": REPO,
        "event": event,
        "sha": sha,
        "workkey": workkey,
    }
    if pr is not None:
        body["pr"] = pr
    return body


def _task():
    return {
        "adapter": "local",
        "params": {"unit": "a"},
        "effect_class": "idempotent",
        "max_attempts": 1,
        "lease_ttl_s": 30,
        "estimated_cost_eur": 0.0,
    }


def _pull(merged=True, sha=SHA, base="integration/v1"):
    return {"merged": merged, "merge_commit_sha": sha, "base": {"ref": base}}


class FakeHTTP:
    def __init__(self):
        self.comments = []
        self.pulls = {}
        self.checks = {}
        self.down = False
        self.tasks = []
        self.seen = set()

    def __call__(self, method, url, headers, body, timeout):
        assert timeout > 0
        assert TOKEN not in url
        if "127.0.0.1" in url:
            assert headers.get("X-Courier-Token") == TOKEN
            if self.down:
                raise OSError("controller unreachable")
            assert method == "POST" and url.endswith("/v1/tasks")
            posted = json.loads(body.decode("utf-8"))
            key = posted["idempotency_key"]
            duplicate = key in self.seen
            self.seen.add(key)
            if not duplicate:
                self.tasks.append(posted)
            status = 200 if duplicate else 201
            return status, json.dumps({"task_id": "task-1", "duplicate": duplicate}).encode()
        assert url.startswith("https://api.github.com/")
        assert "page=2" not in url
        listing = "/comments?" in url or "/check-runs" in url
        if listing:
            assert "per_page=50" in url
        if "/comments?" in url:
            return 200, json.dumps(self.comments).encode()
        if "/pulls/" in url:
            number = int(url.rstrip("/").rsplit("/", 1)[-1])
            repo = url.split("/repos/", 1)[1].split("/pulls/")[0]
            return 200, json.dumps(self.pulls[(repo, number)]).encode()
        if "/check-runs" in url:
            sha = url.split("/commits/", 1)[1].split("/check-runs", 1)[0]
            repo = url.split("/repos/", 1)[1].split("/commits/")[0]
            runs = self.checks[(repo, sha)]
            return 200, json.dumps({"total_count": len(runs), "check_runs": runs}).encode()
        raise AssertionError(url)


def _home(tmp_path, parked):
    home = tmp_path / "home"
    (home / "run").mkdir(parents=True)
    (home / "run" / "controller.token").write_text(TOKEN + "\n", encoding="utf-8")
    (home / "parked_workkeys.json").write_text(json.dumps(parked), encoding="utf-8")
    return home


def _run(tmp_path, http, parked, comments, *, extra=None):
    http.comments = comments
    home = _home(tmp_path, parked)
    out, err = [], []
    code = main(
        [
            "--repo", REPO,
            "--inbox-issue", "15",
            "--courier-home", str(home),
            "--controller", "http://127.0.0.1:9",
            "--allow-login", "octo",
            *(extra or []),
        ],
        http=http,
        stdout=out.append,
        stderr=err.append,
    )
    log_path = home / "run" / "github_wake.log"
    log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    cursor = home / "run" / "github_wake.cursor"
    return code, http, home, "".join(out), "".join(err), log, cursor


def test_verified_merge_queues_one_task(tmp_path):
    http = FakeHTTP()
    http.pulls[(REPO, 7)] = _pull()
    code, http, home, out, err, log, cursor = _run(
        tmp_path, http,
        {"wk-a": {"depends_on": [{"repo": REPO, "pr": 7, "sha": SHA}], "task": _task()}},
        [_comment(1, "octo", "OWNER", _wake())],
    )
    assert code == 0
    assert len(http.tasks) == 1
    assert http.tasks[0]["idempotency_key"].startswith("wake:wk-a:")
    assert "estimated_cost_eur" not in http.tasks[0]
    assert http.tasks[0]["params"]["estimated_cost_eur"] == 0.0
    assert json.loads(log)["outcome"] == "queued"
    assert json.loads(cursor.read_text(encoding="utf-8"))["comment_id"] == 1
    assert (home / "parked_workkeys.json").exists()


def test_replay_same_wake_is_duplicate(tmp_path):
    http = FakeHTTP()
    http.pulls[(REPO, 7)] = _pull()
    parked = {"wk-a": {"depends_on": [{"repo": REPO, "pr": 7, "sha": SHA}], "task": _task()}}
    comments = [
        _comment(1, "octo", "OWNER", _wake()),
        _comment(2, "octo", "OWNER", _wake(), updated="2026-10-08T04:01:00Z"),
    ]
    code, http, home, out, err, log, cursor = _run(tmp_path, http, parked, comments)
    assert code == 0
    assert len(http.tasks) == 1
    outcomes = [json.loads(line)["outcome"] for line in log.splitlines()]
    assert outcomes == ["queued", "duplicate"]


def test_non_owner_and_non_allowlisted_are_ignored(tmp_path):
    http = FakeHTTP()
    http.pulls[(REPO, 7)] = _pull()
    comments = [
        _comment(1, "stranger", "OWNER", _wake(wake_id="nope")),
        _comment(2, "octo", "COLLABORATOR", _wake(wake_id="also-nope"), updated="2026-10-08T04:01:00Z"),
    ]
    code, http, home, out, err, log, cursor = _run(
        tmp_path, http,
        {"wk-a": {"depends_on": [{"repo": REPO, "pr": 7}], "task": _task()}},
        comments,
    )
    assert code == 0 and http.tasks == []
    lines = [json.loads(line) for line in log.splitlines()]
    assert lines == [{"comment_id": 1, "outcome": "ignored"}, {"comment_id": 2, "outcome": "ignored"}]
    assert "nope" not in log and "courier.wake" not in log


def test_unverified_merge_creates_no_task(tmp_path):
    http = FakeHTTP()
    http.pulls[(REPO, 7)] = _pull(merged=False)
    code, http, *_rest = _run(
        tmp_path, http,
        {"wk-a": {"depends_on": [{"repo": REPO, "pr": 7, "sha": SHA}], "task": _task()}},
        [_comment(1, "octo", "OWNER", _wake())],
    )
    assert code == 0 and http.tasks == []
    http.pulls[(REPO, 7)] = _pull(sha=SHA2)
    code2, http2, home, out, err, log, cursor = _run(
        tmp_path / "sha", http,
        {"wk-a": {"depends_on": [{"repo": REPO, "pr": 7, "sha": SHA}], "task": _task()}},
        [_comment(1, "octo", "OWNER", _wake())],
    )
    assert code2 == 0 and http2.tasks == []
    assert "unverified" in log


def test_unknown_workkey_is_ignored(tmp_path):
    http = FakeHTTP()
    http.pulls[(REPO, 7)] = _pull()
    code, http, home, out, err, log, cursor = _run(
        tmp_path, http,
        {"other": {"depends_on": [{"repo": REPO, "pr": 7}], "task": _task()}},
        [_comment(1, "octo", "OWNER", _wake(workkey="missing"))],
    )
    assert code == 0 and http.tasks == []
    assert json.loads(log)["outcome"] == "ignored"
    assert json.loads(log)["workkey"] == "missing"


def test_cursor_without_comment_id_does_not_replay(tmp_path):
    http = FakeHTTP()
    http.pulls[(REPO, 7)] = _pull()
    home = _home(
        tmp_path,
        {"wk-a": {"depends_on": [{"repo": REPO, "pr": 7, "sha": SHA}], "task": _task()}},
    )
    (home / "run" / "github_wake.cursor").write_text(
        json.dumps({"updated_at": "2026-10-08T04:00:00Z"}) + "\n",
        encoding="utf-8",
    )
    http.comments = [_comment(1, "octo", "OWNER", _wake())]
    err = []
    code = main(
        [
            "--repo", REPO,
            "--inbox-issue", "15",
            "--courier-home", str(home),
            "--controller", "http://127.0.0.1:9",
            "--allow-login", "octo",
        ],
        http=http,
        stdout=lambda _line: None,
        stderr=err.append,
    )
    assert code == 2
    assert http.tasks == []
    assert "malformed local wake state" in "".join(err)


def test_controller_down_exits_75_and_keeps_cursor(tmp_path):
    http = FakeHTTP()
    http.down = True
    http.pulls[(REPO, 7)] = _pull()
    code, http, home, out, err, log, cursor = _run(
        tmp_path, http,
        {"wk-a": {"depends_on": [{"repo": REPO, "pr": 7, "sha": SHA}], "task": _task()}},
        [_comment(1, "octo", "OWNER", _wake())],
    )
    assert code == 75
    assert http.tasks == []
    assert not cursor.exists()
    assert "queued" not in log


def test_partial_dependencies_stay_parked(tmp_path):
    http = FakeHTTP()
    http.pulls[(REPO, 7)] = _pull()
    http.pulls[(REPO, 8)] = _pull(merged=False, sha=SHA2)
    parked = {
        "wk-a": {
            "depends_on": [
                {"repo": REPO, "pr": 7, "sha": SHA},
                {"repo": REPO, "pr": 8, "sha": SHA2},
            ],
            "task": _task(),
        }
    }
    before = json.dumps(parked)
    code, http, home, out, err, log, cursor = _run(
        tmp_path, http, parked, [_comment(1, "octo", "OWNER", _wake())],
    )
    assert code == 0 and http.tasks == []
    assert json.loads(log)["outcome"] == "not_satisfied"
    assert (home / "parked_workkeys.json").read_text(encoding="utf-8") == before


def test_failing_check_run_does_not_wake(tmp_path):
    http = FakeHTTP()
    http.checks[(REPO, SHA)] = [{"status": "completed", "conclusion": "failure"}]
    code, http, home, out, err, log, cursor = _run(
        tmp_path, http,
        {"wk-a": {"depends_on": [{"repo": REPO, "sha": SHA}], "task": _task()}},
        [_comment(1, "octo", "OWNER", _wake(event="ci_passed", pr=None))],
    )
    assert code == 0 and http.tasks == []
    assert json.loads(log)["outcome"] == "unverified"


def test_token_never_appears_in_stdout_stderr_or_log(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
    http = FakeHTTP()
    http.pulls[(REPO, 7)] = _pull()
    code, http, home, out, err, log, cursor = _run(
        tmp_path, http,
        {"wk-a": {"depends_on": [{"repo": REPO, "pr": 7, "sha": SHA}], "task": _task()}},
        [_comment(1, "octo", "OWNER", _wake())],
    )
    assert code == 0 and len(http.tasks) == 1
    blob = out + err + log + cursor.read_text(encoding="utf-8")
    assert TOKEN not in blob
    assert "Bearer" not in out + err + log


def _blocked(tmp_path, task, *, entry_extra=None, extra=None, second=None):
    http = FakeHTTP()
    http.pulls[(REPO, 7)] = _pull()
    parked = {"wk-a": {"depends_on": [{"repo": REPO, "pr": 7, "sha": SHA}], "task": task}}
    if entry_extra:
        parked["wk-a"].update(entry_extra)
    comments = [_comment(1, "octo", "OWNER", _wake())]
    if second is not None:
        parked["wk-b"] = {"depends_on": [{"repo": REPO, "pr": 7, "sha": SHA}], "task": second}
        comments.append(
            _comment(2, "octo", "OWNER", _wake(wake_id="w-b", workkey="wk-b"), updated="2026-10-08T04:01:00Z")
        )
    return _run(tmp_path, http, parked, comments, extra=extra)


def test_missing_cost_is_blocked_and_not_posted(tmp_path):
    task = _task()
    del task["estimated_cost_eur"]
    code, http, home, out, err, log, cursor = _blocked(tmp_path, task)
    assert code == 2
    assert http.tasks == []
    record = json.loads(log)
    assert record["outcome"] == "blocked"
    assert record["reason"] == "UNKNOWN_COST"
    assert json.loads(cursor.read_text(encoding="utf-8"))["comment_id"] == 1


def test_unknown_cost_flag_is_blocked_and_not_posted(tmp_path):
    task = _task()
    task["unknown_cost"] = True
    code, http, home, out, err, log, cursor = _blocked(tmp_path, task)
    assert code == 2 and http.tasks == []
    assert json.loads(log)["reason"] == "UNKNOWN_COST"


def test_unknown_cost_class_is_blocked_and_not_posted(tmp_path):
    task = _task()
    task["cost_class"] = "unknown"
    code, http, home, out, err, log, cursor = _blocked(tmp_path, task)
    assert code == 2 and http.tasks == []
    assert json.loads(log)["reason"] == "UNKNOWN_COST"


def test_negative_cost_is_blocked_and_not_posted(tmp_path):
    task = _task()
    task["estimated_cost_eur"] = -1.0
    code, http, home, out, err, log, cursor = _blocked(tmp_path, task)
    assert code == 2 and http.tasks == []
    assert json.loads(log)["reason"] == "UNKNOWN_COST"


def test_positive_cost_is_blocked_and_not_posted(tmp_path):
    task = _task()
    task["estimated_cost_eur"] = 99.0
    code, http, home, out, err, log, cursor = _blocked(tmp_path, task)
    assert code == 2 and http.tasks == []
    assert json.loads(log)["reason"] == "SPEND_NOT_ALLOWED_BY_POLICY"


def test_params_unknown_cost_is_blocked_and_not_posted(tmp_path):
    task = _task()
    task["params"] = {"unit": "a", "unknown_cost": True}
    code, http, home, out, err, log, cursor = _blocked(tmp_path, task)
    assert code == 2 and http.tasks == []
    assert json.loads(log)["reason"] == "UNKNOWN_COST"


def test_entry_mark_is_not_hidden_by_task_zero(tmp_path):
    code, http, home, out, err, log, cursor = _blocked(
        tmp_path, _task(), entry_extra={"unknown_cost": True},
    )
    assert code == 2 and http.tasks == []
    assert json.loads(log)["reason"] == "UNKNOWN_COST"


def test_entry_level_zero_cost_is_posted_inside_params(tmp_path):
    task = _task()
    del task["estimated_cost_eur"]
    code, http, home, out, err, log, cursor = _blocked(
        tmp_path, task, entry_extra={"estimated_cost_eur": 0.0},
    )
    assert code == 0
    assert len(http.tasks) == 1
    assert "estimated_cost_eur" not in http.tasks[0]
    assert http.tasks[0]["params"]["estimated_cost_eur"] == 0.0
    assert json.loads(log)["outcome"] == "queued"


def test_dry_run_blocked_cost_is_not_queued(tmp_path):
    task = _task()
    del task["estimated_cost_eur"]
    code, http, home, out, err, log, cursor = _blocked(tmp_path, task, extra=["--dry-run"])
    assert code == 2
    assert http.tasks == []
    assert json.loads(out)["outcome"] == "blocked"
    assert "queued" not in out
    assert log == ""
    assert not cursor.exists()


def test_blocked_wake_does_not_stall_the_next_one(tmp_path):
    missing = _task()
    del missing["estimated_cost_eur"]
    code, http, home, out, err, log, cursor = _blocked(tmp_path, missing, second=_task())
    assert code == 2
    assert len(http.tasks) == 1
    assert http.tasks[0]["idempotency_key"].startswith("wake:wk-b:")
    outcomes = [json.loads(line)["outcome"] for line in log.splitlines()]
    assert outcomes == ["blocked", "queued"]
    assert json.loads(cursor.read_text(encoding="utf-8"))["comment_id"] == 2


def test_dry_run_does_not_consume_an_ignored_comment(tmp_path):
    http = FakeHTTP()
    code, http, home, out, err, log, cursor = _run(
        tmp_path, http,
        {"wk-a": {"depends_on": [{"repo": REPO, "pr": 7}], "task": _task()}},
        [_comment(1, "stranger", "OWNER", _wake())],
        extra=["--dry-run"],
    )
    assert code == 0 and http.tasks == []
    assert json.loads(out)["outcome"] == "ignored"
    assert log == ""
    assert not cursor.exists()


def test_dry_run_of_an_admitted_wake_does_not_post_or_advance(tmp_path):
    http = FakeHTTP()
    http.pulls[(REPO, 7)] = _pull()
    code, http, home, out, err, log, cursor = _run(
        tmp_path, http,
        {"wk-a": {"depends_on": [{"repo": REPO, "pr": 7, "sha": SHA}], "task": _task()}},
        [_comment(1, "octo", "OWNER", _wake())],
        extra=["--dry-run"],
    )
    assert code == 0 and http.tasks == []
    assert json.loads(out)["outcome"] == "queued"
    assert log == ""
    assert not cursor.exists()
