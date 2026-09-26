"""Abnahmetests YOLO-Profil. Hermetisch: Temp-Repos, Fake-Muse, kein Netz, kein echtes Muse, nichts im Original."""
import hashlib, json, os, re, shutil, subprocess, sys, threading, time, types
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
import cannon_yolo as y

HTML_SHA = "27e3caf1ed3661d2f8dfdcb5cc47860dab1dff52bcd916edcf303829cbd23765"
CSS_SHA = "dae4912480b5a37be4e22624f470da9727b6ff8c289583263493de7d46391555"
PRE, POST = os.environ.get("COURIER_TAG_PRE", "pre-yolo-patch"), os.environ.get("COURIER_TAG_POST", "yolo-patch-applied")


def _have_yolo_tags():
    for ref in (PRE, POST):
        r = subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref],
                           cwd=ROOT, capture_output=True)
        if r.returncode != 0:
            return False
    return True


needs_yolo_tags = pytest.mark.skipif(
    not _have_yolo_tags(), reason="yolo baseline tags missing")
ALLOWED = {"app/cannon.js", "app/cannon/web.py", "scripts/cannon_motor.py", "scripts/cannon_yolo.py",
           "tests/test_cannon_yolo.py", "tests/dom_harness.js"}
# Status-JSON wie /api/cannon/status (app/cannon/web.py:status() + app/cannon.js:refresh())
STATUS = {"state": {"status": "RUNNING", "metrics": {"DONE": 5}, "counts": {"QUEUED": 0, "RESULT_RECEIVED": 0}, "lanes": {"w1": {"phase": "RUNNING", "task": {"task_id": "0001"}}}, "active_lanes": 1, "last_result": "alt"}, "session": {"remaining": 999999995, "count": 5, "mode": "BEGRENZT", "target": 1000000000}, "helper_active": True, "helper_exit": None, "loaded_build": "x", "source_build": "x", "error": None}

FAKE = r'''#!/usr/bin/env python3
import json, os, subprocess, sys, time
a = sys.argv; ws = a[a.index("--workspace") + 1]; tid = open(a[a.index("--prompt-file") + 1], encoding="utf-8").readline().split()[-1]
m = os.environ.get("FAKE_MODE", "ok")
say = lambda t: print(json.dumps({"type": "msg", "text": t}), flush=True)
blk = lambda st="ERLEDIGT", i=None, err="-": "COURIER-ERGEBNIS\nAufgabe: %s\nStatus: %s\nGeändert: x\nBeleg: ok\nFehler: %s\nENDE-COURIER" % (i or tid, st, err)
def w(p, t="x\n"): open(p, "a").write(t)
if m == "empty": sys.exit(0)
if m == "noblock": say("fertig ohne Format"); sys.exit(0)
if m == "ask": say("Soll ich weitermachen? proceed (1/2)"); time.sleep(60)
if m == "hang": say("arbeite weiter und weiter"); time.sleep(60)
if m == "silent": time.sleep(60)
if m == "fail": say(blk("FEHLER", err="kaputt")); sys.exit(0)
if m == "crash": say("boom"); sys.exit(3)
if m == "wrongid": say(blk(i="9999")); sys.exit(0)
w(os.path.join(ws, "out_%s.txt" % tid))
if m == "tag": subprocess.run(["git", "-C", os.environ["FAKE_REPO"], "tag", "-d", "rescue-1"], check=True)
if m == "desk": w(os.environ["FAKE_DESKTOP"])
if m == "pathhit": w(os.path.join(ws, "app/cannon.html"))
if m == "secret": w(os.path.join(ws, "leak.txt"), "k=AKIA" + "ABCDEFGHIJKLMNOP\n")
if m == "rewrite": subprocess.run(["git", "reset", "-q", "--hard", "HEAD~1"], cwd=ws, check=True)
if m == "leak": say("Key AKIA" + "ABCDEFGHIJKLMNOP host 10.1.2.3 fertig")
if m == "delta":
    for ch in blk().splitlines(True): print(json.dumps({"delta": ch}), flush=True)
    sys.exit(0)
if m == "dup": say(blk())
say("erledigt"); say(blk())
'''


@pytest.fixture
def W(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir()
    ge = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x", "GIT_CONFIG_GLOBAL": os.devnull}
    g = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True, text=True, env=ge).stdout.strip()
    g("init", "-q", "-b", "main"); (repo / "app").mkdir(); (repo / "tasks").mkdir(); (repo / "app/cannon.html").write_text("<html></html>")
    for i in ("0001", "0002", "0003"): (repo / f"tasks/{i}.md").write_text(f"Lege out_{i}.txt an.")
    g("add", "-A"); g("commit", "-qm", "c1"); (repo / "README").write_text("x"); g("add", "-A"); g("commit", "-qm", "c2"); g("tag", "rescue-1")
    fake = tmp_path / "muse"; fake.write_text(FAKE); fake.chmod(0o755)
    (tmp_path / "desk").mkdir(); dk = tmp_path / "desk" / "Courier Symphony Cannon.decoy"; dk.write_text("orig")
    e = {**ge, "COURIER_CANNON_PROFILE": "yolo", "COURIER_CANNON_HOME": str(tmp_path / "home"), "COURIER_CANNON_ROOT": str(repo),
         "COURIER_MUSE_BIN": str(fake), "COURIER_DESKTOP_ITEM": str(dk), "COURIER_YOLO_TASK_SECONDS": "15", "COURIER_YOLO_IDLE_SECONDS": "5",
         "FAKE_REPO": str(repo), "FAKE_DESKTOP": str(dk)}
    return types.SimpleNamespace(repo=repo, g=g, env=e, tmp=tmp_path, fake=fake)


def make(W, mode, **extra):
    e = {**W.env, "FAKE_MODE": mode, **extra}; return y.Yolo({}, env=e), e


def step(s):
    assert s.gate() == "", "gate"
    t = s.next_task(); assert t
    return s.execute(t)


def procs(W): return subprocess.run(["pgrep", "-f", str(W.fake)], capture_output=True).returncode == 0   # True = Muse-Prozess lebt noch


# ---- R: Regeln, Seite unveraendert ----
def test_r1_html_css_byte_identical():
    assert hashlib.sha256((ROOT / "app/cannon.html").read_bytes()).hexdigest() == HTML_SHA
    assert hashlib.sha256((ROOT / "app/cannon.css").read_bytes()).hexdigest() == CSS_SHA


@needs_yolo_tags
def test_r3_only_allowed_files_changed():
    d = subprocess.run(["git", "diff", "--name-only", PRE, POST], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    assert d and set(d) <= ALLOWED, set(d) - ALLOWED


def test_r4_default_profile_is_inactive(tmp_path):
    assert not y.active({}) and y.active({"COURIER_CANNON_PROFILE": "yolo"})
    assert y.live_payload({"COURIER_CANNON_LIVE": str(tmp_path / "none.json")}) is None


# ---- D: Anzeige nur per JS in vorhandenen Elementen ----
def dom(js_text, status, tmp):
    assert shutil.which("node"), "node fehlt"
    (tmp / "c.js").write_text(js_text, encoding="utf-8"); (tmp / "s.json").write_text(json.dumps(status))
    r = subprocess.run(["node", str(ROOT / "tests/dom_harness.js"), str(tmp / "c.js"), str(tmp / "s.json"), "3"], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


old_js = lambda: subprocess.run(["git", "show", PRE + ":app/cannon.js"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
new_js = lambda: (ROOT / "app/cannon.js").read_text(encoding="utf-8")


@needs_yolo_tags
def test_d1_golden_without_live_identical_dom_writes(tmp_path):
    n, o = dom(new_js(), STATUS, tmp_path), dom(old_js(), STATUS, tmp_path)
    assert n == o and not [x for x in n if x[0] == "!"], n


@pytest.mark.skip("UI out of scope")
def test_d2_live_text_only_in_result_and_written_once(tmp_path):
    txt = "LÄUFT · 0001\n\nprint('x')"; st = {**STATUS, "live": {"phase": "LÄUFT", "text": txt}}
    n, o = dom(new_js(), st, tmp_path), dom(old_js(), st, tmp_path)
    res = lambda L: [x for x in L if x[:2] == ["result", "textContent"]]
    assert [x for x in n if x not in res(n)] == [x for x in o if x not in res(o)]      # sonst nichts anders
    assert res(n) == [["result", "textContent", txt]]                                   # 1 Schreibzugriff bei 4 Refreshes: Markierung bleibt


@pytest.mark.skip("UI out of scope")
@needs_yolo_tags
def test_d4_new_js_lines_use_no_new_dom_api_or_ids():
    add = "\n".join(l[1:] for l in subprocess.run(["git", "diff", "-U0", PRE, "--", "app/cannon.js"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
                    if l.startswith("+") and not l.startswith("+++"))
    assert add and not re.search(r"innerHTML|outerHTML|createElement|classList|\.style|appendChild|insertAdjacent|setAttribute|document\.write|eval\(|new Function", add)
    ids = set(re.findall(r'id="([\w-]+)"', (ROOT / "app/cannon.html").read_text(encoding="utf-8")))
    assert set(re.findall(r"\$\('([\w-]+)'\)", add)) <= ids


def test_d5_redact_hides_secrets_keeps_code():
    bad = ["AKIA" + "ABCDEFGHIJKLMNOP", "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2", "-----BEGIN RSA " + "PRIVATE KEY-----\nMIIE\n-----END RSA " + "PRIVATE KEY-----",
           "Bearer abcdef123456", "password=hunter2", "10.20.30.40", "ec2-3-120-1-2.eu-central-1.compute.amazonaws.com",
           "x-symphony-token: abc123def456", "aws_secret_access_key = wJalrXUtnFEMI/K7MDENG+" + "bPxRfiCYEXAMPLEKEY"]
    for b in bad:
        out = y.redact("vor " + b + " nach")
        assert out != "vor " + b + " nach" and not re.search(r"hunter2|10\.20|abcdef123456|MIIE|EXAMPLEKEY|ABCDEFGHIJKLMNOP|3-120-1-2|abc123def456", out), out
    good = ["def f(x): return x + 1", "1.2.3 released 2026-09-21", "tests/test_cannon_yolo.py::test_d5 PASSED",
            "/Users/d/2026-courier/scripts/cannon_motor.py:271", "test_done_only_after_persist_verify_reconcile"]
    assert all(y.redact(g) == g for g in good)


# ---- G: Leitplanken ----
def test_g1_workspace_is_isolated_clone(W):
    s, _ = make(W, "ok"); assert s.gate() == ""
    assert s.ws != W.repo and (s.ws / ".git").is_file() and str(s.ws).startswith(str(W.tmp / "home"))
    assert y.git("remote", gd=s.gd) == "" and y.git("branch", "--show-current", gd=s.gd, wt=s.ws) == s.s["branch"]


def test_g7_child_env_has_no_secrets():
    e = y.child_env({"PATH": "/bin", "AWS_SECRET_ACCESS_KEY": "x", "GITHUB_TOKEN": "t", "SSH_AUTH_SOCK": "s", "SYMPHONY_TOKEN": "s",
                     "MUSE_API_KEY": "m", "COURIER_CANNON_HOME": "/h", "MY_PASSWORD": "p"})
    assert e["PATH"] == "/bin" and e["MUSE_API_KEY"] == "m" and e["GIT_TERMINAL_PROMPT"] == "0"
    assert not {"AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN", "SSH_AUTH_SOCK", "SYMPHONY_TOKEN", "COURIER_CANNON_HOME", "MY_PASSWORD"} & set(e)


def test_g8_command_has_approval_off_sandbox_on(W):
    s, _ = make(W, "ok"); s.gate(); c = s.command("/p")
    assert "--disable-approval" in c and "--disable-web-tools" in c and "--prompt-file" in c and c[c.index("--workspace") + 1] == str(s.ws)
    assert "--yolo" not in c and "--disable-sandbox" not in c


@pytest.mark.parametrize("mode,exp", [("tag", "GUARD_REFS"), ("desk", "GUARD_DESKTOP"), ("pathhit", "GUARD_PATH:app/cannon.html"),
                                      ("secret", "GUARD_SECRET"), ("rewrite", "GUARD_HISTORY")])
def test_g_guards_block_and_integrate_nothing(W, mode, exp):
    sha = W.g("rev-parse", "rescue-1"); s, _ = make(W, mode); k, d, _r = step(s)
    assert (k, d) == ("unknown", exp)
    assert not W.g("branch", "--list", s.s["branch"]) and W.g("rev-parse", "rescue-1") == sha      # nichts integriert, Rettungspunkt intakt


def test_g_preflight_refuses(W):
    for k, v, exp in (("COURIER_DESKTOP_ITEM", str(W.tmp / "none*"), "PREFLIGHT:DESKTOP_ELEMENT_FEHLT"),
                      ("COURIER_MUSE_BIN", "", "PREFLIGHT:MUSE_FEHLT")):
        s, _ = make(W, "ok", **{k: v, "PATH": "/nonexistent"}); assert s.gate() == exp
    (W.tmp / "home").mkdir(); (W.tmp / "home/STOP").write_text("")
    s, _ = make(W, "ok"); assert s.gate() == "PREFLIGHT:STOP_DATEI"


# ---- U: Erledigt nur bei eindeutigem Beleg, alles andere UNKNOWN ----
def test_u1_done_integrates_only_own_branch(W):
    s, _ = make(W, "ok"); before = (W.g("status", "--porcelain"), W.g("rev-parse", "HEAD"), W.g("tag"))
    k, d, res = step(s); br = s.s["branch"]
    assert (k, d) == ("done", "") and res["Status"] == "ERLEDIGT"
    assert "Cannon-Task: 0001" in W.g("log", "-1", "--format=%B", br) and W.g("show", f"{br}:out_0001.txt") == "x"
    assert (W.g("status", "--porcelain"), W.g("rev-parse", "HEAD"), W.g("tag")) == before      # echtes Repo unberuehrt


@pytest.mark.parametrize("mode,exp,extra", [("empty", "LEER", {}), ("noblock", "KEIN_BLOCK", {}), ("wrongid", "KEIN_BLOCK", {}), ("crash", "EXIT_3", {}),
                                            ("ask", "IDLE", {}), ("silent", "IDLE", {}), ("hang", "ZEIT", {"COURIER_YOLO_IDLE_SECONDS": "100", "COURIER_YOLO_TASK_SECONDS": "3"})])
def test_u_unclear_is_unknown_and_process_is_dead(W, mode, exp, extra):
    s, _ = make(W, mode, **extra); t0 = time.time(); k, d, _r = step(s)
    assert (k, d) == ("unknown", exp) and time.time() - t0 < 15 and not procs(W)


@pytest.mark.parametrize("mode", ["dup", "delta"])
def test_u_duplicate_and_streamed_block_still_done(W, mode):
    assert step(make(W, mode)[0])[:2] == ("done", "")


def test_u_fail_is_failed_reset_and_no_retry(W):
    s, _ = make(W, "fail"); assert step(s)[:2] == ("failed", "kaputt")
    assert not W.g("branch", "--list", s.s["branch"]) and not (s.ws / "out_0001.txt").exists()
    assert step(s)[0] == "failed" and s.gate() == "SERIENFEHLER"


# ---- L: Limits und Notaus ----
def test_l_defaults_are_finite_and_hard_limits_trigger(W):
    assert all(v > 0 for k, v in y.cfg({}).items() if k not in ("effort", "glob"))
    T = [time.time()]; s = y.Yolo({}, env={**W.env, "COURIER_YOLO_MAX_TASKS": "3"}, now=lambda: T[0])
    assert s.gate() == ""; T[0] += 4 * 3600 + 1; assert s.gate() == "LIMIT_ZEIT"
    T[0] = time.time(); s.s["deadline"] = T[0] + 99; s.s["tasks_left"] = 0; assert s.gate() == "LIMIT_KONTINGENT"


def test_l_three_tasks_serial_then_quota_stop(W):
    s, _ = make(W, "ok", COURIER_YOLO_MAX_TASKS="3")
    assert [step(s)[0] for _ in range(3)] == ["done"] * 3 and s.gate() == "LIMIT_KONTINGENT"
    assert W.g("log", "--format=%s", s.s["branch"]).splitlines()[:3] == ["Cannon 0003", "Cannon 0002", "Cannon 0001"]


def test_l_kill_switch_stops_running_muse_and_freezes_last_output(W):
    s, e = make(W, "hang", COURIER_YOLO_IDLE_SECONDS="100", COURIER_YOLO_TASK_SECONDS="100")
    assert s.gate() == ""; t = s.next_task()
    threading.Timer(1.0, lambda: (s.home / "STOP").write_text("")).start(); t0 = time.time()
    k, d, _r = s.execute(t); assert (k, d) == ("unknown", "NOTAUS") and time.time() - t0 < 10 and not procs(W) and s.gate() == "NOTAUS"
    s.end("NOTAUS"); lv = y.live_payload(e)
    assert lv["text"].startswith("GESTOPPT · 0001 · NOTAUS") and "arbeite weiter und weiter" in lv["text"]      # letzter Code/Ausgabe bleibt stehen


# ---- S: Zustand und Wiederaufnahme ----
def test_s_recover_table():
    R = y.recover
    assert R("CLAIMED", True, "h", True, "h", None, False) == "RERUN" and R("COMMITTED", True, "c", True, "h", "c", False) == "INTEGRATE"
    assert "UNKNOWN" == R("CLAIMED", True, "h2", True, "h", None, False) == R("EXEC", True, "h", True, "h", None, False) \
        == R("CLAIMED", True, "h", True, "h", None, True) == R("CLAIMED", False, "h", True, "h", None, False)


def test_s_crash_mid_exec_is_unknown_without_second_start(W):
    s, _ = make(W, "ok"); assert s.gate() == ""; t = s.next_task()
    s.s.update(phase="EXEC", task=t, before=s._wg("rev-parse", "HEAD"), pid=999999)
    assert s.execute(t)[:2] == ("unknown", "LEFTOVER") and not (s.ws / "out_0001.txt").exists()


def test_s_claimed_but_never_started_reruns_and_restart_resumes_same_run(W):
    s, e = make(W, "ok"); assert s.gate() == ""; t = s.next_task()
    s.s.update(phase="CLAIMED", task=t, before=s._wg("rev-parse", "HEAD"))
    s2 = y.Yolo(json.loads(json.dumps(s.s)), env=e); assert s2.gate() == "" and s2.s["run"] == s.s["run"]      # Neustart innerhalb 15 min = gleicher Lauf
    assert s2.execute(t)[0] == "done"
    s3 = y.Yolo(json.loads(json.dumps(s2.s)), env=e, now=lambda: time.time() + 2000); assert s3.gate() == "" and s3.s["run"] != s2.s["run"]   # spaeter = neuer Lauf


# ---- P/F: Prompt und Aufgabenquelle ----
def test_p_prompt_is_selfcontained_without_questions():
    t = y.build_prompt("0042", "", "", "/w", "yolo/x")
    assert "?" not in t and "proceed" in t and "(1/2)" in t and t.rstrip().endswith("ENDE-COURIER") and "COURIER-ERGEBNIS\nAufgabe: 0042" in t
    assert y.redact(t) == t and not y.has_secret(t)


def test_f_feeder_serial_skips_known_and_bad_names(W):
    (W.repo / "tasks/bad name.md").write_text("x"); W.g("add", "-A"); W.g("commit", "-qm", "m")
    s, _ = make(W, "ok"); assert s.gate() == ""
    assert [s.next_task(known=("0001",)) for _ in range(3)] == ["0002", "0003", None]
    assert s.execute("../x")[:2] == ("unknown", "TASK_UNBEKANNT")


def test_f_endless_text_mode_and_readme_skipped(W):
    (W.repo / "tasks/README.md").write_text("x"); W.g("add", "-A"); W.g("commit", "-qm", "m")
    s, _ = make(W, "ok", COURIER_YOLO_TASK_TEXT="Arbeite den naechsten offenen Ledger-Eintrag ab.")
    assert s.gate() == ""; a, b = s.next_task(), s.next_task(); assert a != b and a.startswith("auto-" + s.s["run"])
    assert s.execute(a)[:2] == ("done", "") and "naechsten offenen Ledger-Eintrag" in (s.home / "prompts" / (a + ".txt")).read_text(encoding="utf-8")
    s2, _ = make(W, "ok"); assert s2.gate() == "" and [s2.next_task() for _ in range(4)] == ["0001", "0002", "0003", None]      # README uebersprungen


def test_u_muse_binary_missing_is_unknown_start_fehler(W):
    s, _ = make(W, "ok", COURIER_MUSE_BIN=str(W.tmp / "nope")); assert step(s)[:2] == ("unknown", "START_FEHLER")


def test_l_live_shows_output_while_running_not_only_at_end(W):
    s, e = make(W, "hang", COURIER_YOLO_IDLE_SECONDS="100", COURIER_YOLO_TASK_SECONDS="100")
    assert s.gate() == ""; t = s.next_task(); th = threading.Thread(target=s.execute, args=(t,)); th.start(); time.sleep(1.5)
    lv = y.live_payload(e); (s.home / "STOP").write_text(""); th.join(15)
    assert lv["phase"] == "LÄUFT" and "arbeite weiter und weiter" in lv["text"] and not th.is_alive()


def test_g_protected_branches_may_only_move_forward(W):
    W.g("branch", "known-good/a", "HEAD~1"); before = y.snap(W.repo); assert "refs/heads/known-good/a" in before
    W.g("branch", "-f", "known-good/a", "HEAD"); assert y.moved(W.repo, before) == {}                       # vorwaerts erlaubt
    W.g("branch", "-f", "known-good/a", "HEAD~1"); W.g("branch", "-f", "known-good/a", "HEAD~1"); before = {**before, "refs/heads/known-good/a": W.g("rev-parse", "HEAD")}
    assert list(y.moved(W.repo, before)) == ["refs/heads/known-good/a"]                                     # rueckwaerts = Verstoss
    W.g("branch", "-D", "known-good/a"); assert list(y.moved(W.repo, before)) == ["refs/heads/known-good/a"]   # geloescht = Verstoss


def test_p_live_text_is_redacted_and_shows_running_task(W):
    s, e = make(W, "leak"); assert step(s)[0] == "done"; lv = y.live_payload(e)
    assert "fertig" in lv["text"] and "AKIA" not in lv["text"] and "10.1.2.3" not in lv["text"] and lv["text"].startswith("FERTIG · 0001")


# ---- M: Motor-Anbindung (Vorlage: test_cannon_motor_acceptance.py, test_web_real_bridge.py) ----
def _m_env_base(W):
    return {"COURIER_CANNON_PROFILE": "yolo", "COURIER_CANNON_HOME": str(W.tmp / "mhome"),
            "COURIER_CANNON_ROOT": str(W.repo), "COURIER_MUSE_BIN": str(W.fake),
            "COURIER_DESKTOP_ITEM": str(W.tmp / "desk" / "Courier Symphony Cannon.decoy")}


def _m_seed(state_dir, n):
    import json as _j
    import subprocess as _sp
    _wq = ROOT / "scripts" / "work_queue.py"
    _sp.check_call([sys.executable, str(_wq), "--state-dir", str(state_dir), "init", "yolo-pk"])
    for i in range(1, n + 1):
        _sp.check_call([sys.executable, str(_wq), "--state-dir", str(state_dir), "add", _j.dumps(
            {"task_id": f"m{i}", "package_id": "yolo-pk", "description": "Repo-Aufgabe m%i" % i,
             "dependencies": [], "read_scopes": [], "write_scopes": [f"scope-{i}"], "status": "READY"})])


def test_m1_three_done_then_quota_stop_no_fourth_claim(W, monkeypatch):
    from scripts.cannon_motor import CannonMotor
    base = _m_env_base(W)
    base["COURIER_YOLO_MAX_TASKS"] = "3"
    for k, v in base.items():
        monkeypatch.setenv(k, v)
    motor_dir = W.tmp / "motor1"
    motor_dir.mkdir()
    _m_seed(motor_dir, 3)
    m = CannonMotor(motor_dir)
    assert m.yolo is not None
    calls = {"n": 0}

    def _fake_execute(tid):
        calls["n"] += 1
        m.yolo.s["tasks_left"] -= 1
        m.yolo.s["steps_left"] -= m.yolo.c["steps"]
        m.yolo.save()
        return ("done", "", {"Aufgabe": tid, "Status": "ERLEDIGT", "Geändert": "x", "Beleg": "ok", "Fehler": "-", "commit": "c%02d" % calls["n"]})
    monkeypatch.setattr(m.yolo, "execute", _fake_execute)
    assert m.start(cooldown=0)["started"] is True
    for _ in range(3):
        r = m.run_step()
        assert r["step"] == "done"
    assert m.m["done_count"] == 3 and m.invariants()["DONE"] == 3
    assert m.yolo.gate() == "LIMIT_KONTINGENT"
    before = m.m["started_count"]
    r = m.run_step()
    assert r["step"] == "yolo_end" and r["reason"] == "LIMIT_KONTINGENT"
    assert calls["n"] == 3 and m.m["started_count"] == before


def test_m2_unknown_blocks_without_counter_change_no_further_claim(W, monkeypatch):
    from scripts.cannon_motor import CannonMotor
    base = _m_env_base(W)
    for k, v in base.items():
        monkeypatch.setenv(k, v)
    motor_dir = W.tmp / "motor2"
    motor_dir.mkdir()
    _m_seed(motor_dir, 2)
    m = CannonMotor(motor_dir)
    assert m.yolo is not None
    monkeypatch.setattr(m.yolo, "execute", lambda tid: ("unknown", "KEIN_BLOCK", None))
    assert m.start(cooldown=0)["started"] is True
    done_before = m.m["done_count"]
    r = m.run_step()
    assert r["step"] == "unknown_halt" and m.state == "BLOCKED"
    snap = m.queue_snapshot()["tasks"]
    assert snap[r["task"]]["status"] == "BLOCKED"
    assert m.m["done_count"] == done_before
    assert m.run_step()["step"] == "noop"


def test_m3_without_profile_no_live_no_module():
    code = ("import sys; "
            "sys.path.insert(0, '.'); "
            "from app.cannon import web; "
            "d = web.status(); "
            "assert 'live' not in d, d.keys(); "
            "assert 'cannon_yolo' not in sys.modules")
    env = {k: v for k, v in os.environ.items() if k != "COURIER_CANNON_PROFILE"}
    r = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), capture_output=True, text=True, env=env, timeout=30)
    assert r.returncode == 0, r.stderr


def test_m4_with_profile_live_text_matches_file(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_CANNON_PROFILE", "yolo")
    lp = tmp_path / "live.json"
    lp.write_text(json.dumps({"phase": "LÄUFT", "text": "hello-live"}), encoding="utf-8")
    monkeypatch.setenv("COURIER_CANNON_LIVE", str(lp))
    for mod in [m for m in list(sys.modules) if m == "cannon_yolo" or m.startswith("cannon_yolo.")]:
        del sys.modules[mod]
    sys.path.insert(0, str(ROOT / "app"))
    from app.cannon import web
    import importlib
    importlib.reload(web)
    d = web.status()
    assert d.get("live", {}).get("text") == "hello-live"


def test_m5_yolo_done_writes_result_artifact_with_commit_sha(W, monkeypatch):
    from scripts.cannon_motor import CannonMotor
    base = _m_env_base(W)
    for k, v in base.items():
        monkeypatch.setenv(k, v)
    motor_dir = W.tmp / "motor5"
    motor_dir.mkdir()
    _m_seed(motor_dir, 1)
    m = CannonMotor(motor_dir)
    assert m.yolo is not None
    commit = "9f2c4a1b8d3e5f60718293a4b5c6d7e8f90a1b2c"

    def _fake_execute(tid):
        m.yolo.s["tasks_left"] -= 1
        m.yolo.s["steps_left"] -= m.yolo.c["steps"]
        m.yolo.save()
        return ("done", "", {"Aufgabe": tid, "Status": "ERLEDIGT", "Geändert": "x", "Beleg": "ok", "Fehler": "-", "commit": commit})
    monkeypatch.setattr(m.yolo, "execute", _fake_execute)
    assert m.start(cooldown=0)["started"] is True
    r = m.run_step()
    assert r["step"] == "done"
    art = m.results_dir / "m1.result.json"
    assert art.exists()
    data = json.loads(art.read_text(encoding="utf-8"))
    assert data["result_id"] == commit
    assert data["task_id"] == "m1"
    assert data["outcome"] == "ok"
    assert isinstance(data.get("yolo"), dict) and data["yolo"].get("commit") == commit
    assert m.invariants()["LOST_RESULTS"] == 0
    assert m.invariants()["DONE"] == 1


def test_m6_yolo_missing_or_bad_artifact_blocks_instead_of_done(W, monkeypatch):
    from scripts.cannon_motor import CannonMotor
    base = _m_env_base(W)
    for k, v in base.items():
        monkeypatch.setenv(k, v)
    commit_a = "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4"
    motor_dir = W.tmp / "motor6a"
    motor_dir.mkdir()
    _m_seed(motor_dir, 1)
    m = CannonMotor(motor_dir)
    assert m.yolo is not None

    def _fake_a(tid):
        m.yolo.s["tasks_left"] -= 1
        m.yolo.s["steps_left"] -= m.yolo.c["steps"]
        m.yolo.save()
        return ("done", "", {"Aufgabe": tid, "Status": "ERLEDIGT", "Geändert": "x", "Beleg": "ok", "Fehler": "-", "commit": commit_a})
    monkeypatch.setattr(m.yolo, "execute", _fake_a)
    orig = m._wq

    def _wq_del(*argv):
        out = orig(*argv)
        if argv and argv[0] == "complete":
            for p in m.results_dir.glob("*.result.json"):
                try:
                    p.unlink()
                except OSError:
                    pass
        return out
    monkeypatch.setattr(m, "_wq", _wq_del)
    assert m.start(cooldown=0)["started"] is True
    r = m.run_step()
    assert r["step"] == "unknown_halt" and m.state == "BLOCKED"
    raw = json.loads((motor_dir / "queue.json").read_text(encoding="utf-8"))
    assert raw["tasks"]["m1"]["status"] == "BLOCKED"
    assert raw["tasks"]["m1"]["block_reason"] == "BRAUCHT_PRUEFUNG"
    assert "m1" in m.m["needs_review"] and m.m["done_count"] == 0
    commit_b = "b1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4"
    motor_dir2 = W.tmp / "motor6b"
    motor_dir2.mkdir()
    _m_seed(motor_dir2, 1)
    m2 = CannonMotor(motor_dir2)
    assert m2.yolo is not None

    def _fake_b(tid):
        m2.yolo.s["tasks_left"] -= 1
        m2.yolo.s["steps_left"] -= m2.yolo.c["steps"]
        m2.yolo.save()
        return ("done", "", {"Aufgabe": tid, "Status": "ERLEDIGT", "Geändert": "x", "Beleg": "ok", "Fehler": "-", "commit": commit_b})
    m2.yolo.execute = _fake_b
    orig2 = m2._wq

    def _wq_bad(*argv):
        out = orig2(*argv)
        if argv and argv[0] == "complete":
            p = m2.results_dir / "m1.result.json"
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                d["result_id"] = "0" * 40
                p.write_text(json.dumps(d), encoding="utf-8")
            except (OSError, ValueError):
                pass
        return out
    m2._wq = _wq_bad
    assert m2.start(cooldown=0)["started"] is True
    r2 = m2.run_step()
    assert r2["step"] == "unknown_halt" and m2.state == "BLOCKED"
    raw2 = json.loads((motor_dir2 / "queue.json").read_text(encoding="utf-8"))
    assert raw2["tasks"]["m1"]["status"] == "BLOCKED"
    assert raw2["tasks"]["m1"]["block_reason"] == "BRAUCHT_PRUEFUNG"
    assert "m1" in m2.m["needs_review"] and m2.m["done_count"] == 0
