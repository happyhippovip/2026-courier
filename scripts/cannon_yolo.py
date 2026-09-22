"""Courier Cannon: YOLO-Profil (neu, additiv). Aktiv nur mit COURIER_CANNON_PROFILE=yolo, sonst kein Effekt.
YOLO heisst hier: --disable-approval (kein proceed/1-2), Sandbox AN, dazu eigene Leitplanken. Nie --yolo/--disable-sandbox.
Einhaengepunkte im Motor: y=Yolo(state); y.gate() -> ""|Stopp-Grund; y.next_task(known) -> id|None; y.execute(id) -> (kind,detail,res); y.end(grund).
Aufgaben = Dateien tasks/*.md im Repo (id = Dateiname ohne .md). Start ohne Button: Umgebungsvariable COURIER_CANNON_PROFILE=yolo."""
from __future__ import annotations
import glob, hashlib, json, os, queue, re, shutil, signal, subprocess, threading, time
from pathlib import Path

PROTECT = ("app/cannon.html", "app/cannon.css", "app/cannon.js", "app/cannon/", "scripts/cannon_", "scripts/headless_night.py",
           "scripts/mac_adapter", "tests/test_cannon_yolo.py", "tests/dom_harness.js", ".git/", ".env")
REFS = ("refs/tags", "refs/heads/known-good", "refs/heads/known-good*", "refs/heads/rescue", "refs/heads/rescue*",
        "refs/heads/rettung", "refs/heads/rettung*", "refs/heads/main", "refs/heads/master")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_SKIP = ("readme", "index", "template")
_E = lambda env: os.environ if env is None else env


def active(env=None): return _E(env).get("COURIER_CANNON_PROFILE") == "yolo"


def cfg(env=None):
    e = _E(env); g = lambda k, d: type(d)(e.get("COURIER_YOLO_" + k, d))
    return dict(max_seconds=g("MAX_SECONDS", 4 * 3600), max_tasks=g("MAX_TASKS", 40), step_budget=g("STEP_BUDGET", 1200),
                task_seconds=g("TASK_SECONDS", 1500), idle_seconds=g("IDLE_SECONDS", 300), max_fails=g("MAX_FAILS", 2),
                steps=g("STEPS", 30), effort=g("EFFORT", "high"), glob=g("TASK_GLOB", "tasks/*.md"))


def home(env=None):
    e = _E(env); return Path(e.get("COURIER_CANNON_HOME") or Path.home() / ".courier_cannon")


def live_path(env=None):
    e = _E(env); return Path(e.get("COURIER_CANNON_LIVE") or home(e) / "live.json")


# ---------- Anzeige-Text: Schluessel/Tokens/IPs verstecken ----------
_KEY = [(re.compile(p, f), r) for p, f, r in (
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S, "[SCHLÜSSEL]"),
    (r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b", 0, "[KEY]"),
    (r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})", 0, "[TOKEN]"))]
_MORE = [(re.compile(p, f), r) for p, f, r in (
    (r"\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}", re.I, r"\1 [TOKEN]"),
    (r"((?:api[_-]?key|secret|token|passwd|password|authorization)\w*[\"']?\s*[:=]\s*[\"']?)[^\s\"',;]+", re.I, r"\1[VERSTECKT]"),
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", 0, "[IP]"),
    (r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b", 0, "[IP]"),
    (r"\b(?:ec2-[\w-]+|ip-\d+-\d+-\d+-\d+)(?:\.[\w.-]+)?", 0, "[HOST]"),
    (r"\b(?=[\w-]*\d)(?=[\w-]*[A-Z])(?=[\w-]*[a-z])[\w-]{32,}\b", 0, "[VERSTECKT]"))]


def redact(t):
    for rx, r in _KEY + _MORE: t = rx.sub(r, t)
    return t


def has_secret(t): return any(rx.search(t) for rx, _ in _KEY)


class Live:
    """Anzeige-Datei (nur Text, nie Entscheidungsgrundlage). Atomar geschrieben, max. 4x/s."""
    def __init__(s, path, n=60, cap=8000):
        s.p, s.n, s.cap, s.head, s.lines, s.phase, s.t, s.dirty = Path(path), n, cap, "", [], "IDLE", 0.0, False

    def _w(s):
        txt = (s.head + "\n\n" if s.head else "") + "\n".join(s.lines)
        s.p.parent.mkdir(parents=True, exist_ok=True); tmp = s.p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"phase": s.phase, "text": redact(txt)[-s.cap:]}, ensure_ascii=False), encoding="utf-8")
        tmp.replace(s.p); s.t, s.dirty = time.time(), False

    def start(s, task): s.phase, s.head, s.lines = "LÄUFT", "LÄUFT · " + task, []; s._w()

    def add(s, line):
        s.lines, s.dirty = (s.lines + [line.rstrip()[:400]])[-s.n:], True
        if time.time() - s.t > 0.25: s._w()

    def flush(s):
        if s.dirty: s._w()

    def freeze(s, phase, why): s.phase, s.head = phase, phase + " · " + why; s._w()


def live_payload(env=None):
    try: d = json.loads(live_path(env).read_text(encoding="utf-8"))
    except Exception: return None
    return d if isinstance(d.get("text"), str) else None


# ---------- Muse-Prozess: Live-Tail, Timeout, Idle, Notaus ----------
def texts(line):
    """-> (alle Strings der Zeile, Strings fuer die Anzeige). JSON-Schema von muse --json ist UNKNOWN, daher generisch."""
    try: o = json.loads(line)
    except ValueError: o = None
    if not isinstance(o, (dict, list)): s = line.rstrip("\n"); return [s], [s]
    out = []
    def w(x):
        if isinstance(x, str): out.append(x)
        elif isinstance(x, dict): [w(v) for v in x.values()]
        elif isinstance(x, list): [w(v) for v in x]
    w(o); return out, [t for t in out if len(t) > 3 and (" " in t or "\n" in t)]


def _kill(p):
    if os.name == "nt": subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True); return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try: os.killpg(p.pid, sig)
        except ProcessLookupError: return
        try: p.wait(3); break
        except subprocess.TimeoutExpired: pass
    try: os.killpg(p.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError): pass


def run_muse(cmd, cwd, env, live, hard_s, idle_s, stop, on_pid=lambda pid: None):
    kw = {} if os.name == "nt" else {"start_new_session": True}
    p = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, errors="replace", bufsize=1, **kw)
    on_pid(p.pid); q = queue.Queue()
    def rd():
        for l in p.stdout: q.put(l)
        q.put(None)
    threading.Thread(target=rd, daemon=True).start()
    t0 = last = time.time(); parts, raw, why, eof = [], [], "", False
    while not eof:
        try:
            l = q.get(timeout=0.2)
            if l is None: eof = True
            else:
                raw.append(l); allt, disp = texts(l); parts += allt; last = time.time()
                for t in disp: [live.add(x) for x in t.splitlines()]
        except queue.Empty: live.flush()
        now = time.time()
        if not eof: why = "NOTAUS" if stop() else "ZEIT" if now - t0 > hard_s else "IDLE" if now - last > idle_s else ""
        if why: _kill(p); break
    return p.wait(), parts, "".join(raw), why


# ---------- Antwortformat, Prompt, UNKNOWN-Erkennung ----------
FORMAT = ("COURIER-ERGEBNIS\nAufgabe: {id}\nStatus: ERLEDIGT oder FEHLER oder BLOCKIERT\nGeändert: Dateien, kommagetrennt, oder -\n"
          "Beleg: ausgeführter Test oder Befehl und Ergebnis in einem Satz\nFehler: Grund in einem Satz oder -\nENDE-COURIER")


def build_prompt(tid, title, body, ws, branch):
    return f"""COURIER-AUFGABE {tid}
Du arbeitest allein und vollautomatisch. Niemand beantwortet Rückfragen. Warte nie auf "proceed" oder eine Auswahl (1/2). Entscheide selbst, nimm bei Unklarheit die sicherste Annahme und nenne sie im Feld Beleg.

ARBEITSORT: {ws} (Git-Arbeitskopie, Branch {branch}). Ändere nur Dateien darin. Committe nicht.
VERBOTEN: git push, git tag, git branch -D, git reset --hard, --force, Dateien außerhalb des Arbeitsorts, Desktop, ~/.ssh, ~/.aws, Schlüssel oder Tokens lesen, ausgeben oder speichern, Änderungen an: {", ".join(PROTECT)}.
Arbeite die Aufgabe vollständig ab und führe die vorhandenen Tests dazu aus.

AUFGABE: {title}
{body.strip()}

ANTWORT: Deine letzte Nachricht besteht nur aus diesem Block, davor und danach steht nichts:
{FORMAT.format(id=tid)}
"""


_BLK = re.compile(r"COURIER-ERGEBNIS[ \t]*\r?\n(.*?)\r?\n[ \t]*ENDE-COURIER", re.S)
_ASK = re.compile(r"proceed|\[y/n\]|\(1/2\)|\b1\s*/\s*2\b|continue\?|weiter\?", re.I)


def parse(variants, tid):
    """Genau ein gueltiger Block fuer diese Aufgabe (identische Duplikate ok), sonst None."""
    for t in variants:
        ok = []
        for b in _BLK.findall(t):
            d = {k: v.strip() for k, v in re.findall(r"^[ \t]*(Aufgabe|Status|Geändert|Beleg|Fehler):[ \t]*(.*)$", b, re.M)}
            if d.get("Status") in ("ERLEDIGT", "FEHLER", "BLOCKIERT") and d.get("Aufgabe") == tid: ok.append(d)
        if ok and all(x == ok[0] for x in ok): return ok[0]
    return None


def classify(rc, variants, raw, tid, why="", bad=""):
    """-> ("done"|"failed"|"unknown", Grund). Alles Unklare ist unknown."""
    if bad or why: return "unknown", bad or why
    if rc != 0: return "unknown", "EXIT_%s" % rc
    if not raw.strip(): return "unknown", "LEER"
    b = parse(variants, tid)
    if not b: return "unknown", "INTERAKTIV" if _ASK.search(raw[-1000:]) else "KEIN_BLOCK"
    return ("done", "") if b["Status"] == "ERLEDIGT" else ("failed", b.get("Fehler") or b["Status"])


_SEC = re.compile(r"KEY|TOKEN|SECRET|PASS|CRED|AUTH", re.I)


def child_env(env=None):
    e = dict(_E(env)); keep = set(filter(None, e.get("COURIER_YOLO_ENV_KEEP", "").split(",")))
    for k in list(e):
        if k not in keep and not k.startswith("MUSE_") and (_SEC.search(k) or k.startswith(("AWS_", "GITHUB_", "GH_", "SSH_", "SYMPHONY_", "COURIER_"))): del e[k]
    e.update(GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="/bin/false", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
             AWS_SHARED_CREDENTIALS_FILE=os.devnull, AWS_CONFIG_FILE=os.devnull)
    return e


# ---------- Git-Leitplanken: Muse arbeitet nur im Klon, das echte Repo wird nur geprueft ----------
def git(*a, repo=None, gd=None, wt=None, check=True):
    pre = ["git", "-c", "core.hooksPath=" + os.devnull, "-c", "core.fsmonitor=false"]
    if gd: pre += ["--git-dir", str(gd)] + (["--work-tree", str(wt)] if wt else [])
    elif repo: pre += ["-C", str(repo)]
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    r = subprocess.run(pre + list(a), capture_output=True, text=True, env=env)
    if check and r.returncode: raise RuntimeError("git %s: %s" % (a[0], r.stderr.strip()[:200]))
    return r.stdout.strip() if check or r.returncode == 0 else ""


def gitok(*a, **k):
    try: git(*a, **k); return True
    except RuntimeError: return False


def snap(repo, extra=()):
    cur = git("symbolic-ref", "-q", "HEAD", repo=repo, check=False)
    out = git("for-each-ref", "--format=%(refname) %(objectname)", *REFS, *extra, *([cur] if cur else []), repo=repo)
    return dict(l.split(" ", 1) for l in out.splitlines() if l)


def moved(repo, before):
    """Geschuetzte Refs, die fehlen oder verschoben wurden (Tags nie; Branches nur vorwaerts erlaubt)."""
    bad = {}
    for r, v in before.items():
        n = git("rev-parse", "-q", "--verify", r, repo=repo, check=False)
        if n != v and (r.startswith("refs/tags/") or not n or not gitok("merge-base", "--is-ancestor", v, n, repo=repo)): bad[r] = v
    return bad


def fp(paths):
    h = hashlib.sha256()
    for p in sorted(str(x) for x in paths):
        h.update(p.encode()); q = Path(p)
        for f in [q] if q.is_file() else sorted(q.rglob("*")) if q.is_dir() else []:
            if "__pycache__" in f.parts: continue
            try:
                st = f.stat(); h.update(("|%s|%s|%s" % (f, st.st_size, st.st_mtime_ns)).encode())
                if f.is_file() and st.st_size <= 1 << 20: h.update(f.read_bytes())
            except OSError: pass
    return h.hexdigest()


def prepare(repo, base, run):
    root = Path(base) / "yolo" / run; ws, gd = root / "ws", root / "git"; root.mkdir(parents=True)
    git("clone", "-q", "--no-hardlinks", "--separate-git-dir", str(gd), str(repo), str(ws))
    git("remote", "remove", "origin", gd=gd)
    for k, v in (("user.name", "Courier Cannon"), ("user.email", "cannon@localhost"), ("core.hooksPath", os.devnull)): git("config", k, v, gd=gd)
    git("checkout", "-q", "-b", "yolo/" + run, gd=gd, wt=ws)
    return ws, gd


def check_ws(gd, ws, base):
    if not gitok("merge-base", "--is-ancestor", base, "HEAD", gd=gd): return "GUARD_HISTORY"
    for n in filter(None, git("diff", "--name-only", "-z", base, "HEAD", gd=gd, wt=ws).split("\0")):
        if n.startswith(PROTECT + ("../",)): return "GUARD_PATH:" + n
        if re.search(r"(^|/)(id_rsa[^/]*|[^/]*\.(pem|key|p12)|credentials)$", n): return "GUARD_SECRET:" + n
    add = "\n".join(l[1:] for l in git("diff", "-U0", base, "HEAD", gd=gd, wt=ws).splitlines() if l.startswith("+") and not l.startswith("+++"))
    return "GUARD_SECRET" if has_secret(add) else ""


def recover(ph, same, head, clean, before, commit, alive):
    """Wiederaufnahme nach Absturz: nur eindeutige Faelle, sonst UNKNOWN (kein Retry)."""
    if not same or alive: return "UNKNOWN"
    if ph == "CLAIMED" and clean and head == before: return "RERUN"
    if ph == "COMMITTED" and head == commit: return "INTEGRATE"
    return "UNKNOWN"


def _alive(pid):
    if not pid: return False
    try: os.kill(pid, 0)
    except OSError: return False
    return True


class Yolo:
    def __init__(s, state, save=lambda: None, env=None, now=time.time):
        s.s, s.save, s.env, s.now, s.ready = state, save, _E(env), now, False
        s.home = home(s.env); s.live = Live(live_path(s.env)); s.s.setdefault("seen", [])

    def stopped(s): return (s.home / "STOP").exists()

    def begin(s):
        st, e = s.s, s.env
        try: c = s.c = cfg(e)
        except ValueError: return "PREFLIGHT:CONFIG"
        if ".." in c["glob"] or c["glob"].startswith("/"): return "PREFLIGHT:TASK_GLOB"
        s.muse = e.get("COURIER_MUSE_BIN") or shutil.which("muse", path=e.get("PATH"))
        s.repo = Path(e.get("COURIER_CANNON_ROOT") or Path(__file__).resolve().parents[1])
        d = e.get("COURIER_DESKTOP_ITEM", str(Path.home() / "Desktop" / "Courier Symphony Cannon*"))
        s.desk = [] if d == "-" else sorted(glob.glob(os.path.expanduser(d)))
        s.pins = sorted({m for p in PROTECT if p != ".git/" for m in glob.glob(str(s.repo / p) + "*")})
        if not s.muse: return "PREFLIGHT:MUSE_FEHLT"
        if d != "-" and not s.desk: return "PREFLIGHT:DESKTOP_ELEMENT_FEHLT"
        if s.stopped(): return "PREFLIGHT:STOP_DATEI"
        resume = (st.get("active") and s.now() - st.get("hb", 0) < 900 and Path(st.get("ws", "")).is_dir()
                    and st.get("tasks_left", 0) > 0 and s.now() < st.get("deadline", 0))
        if not resume:
            run = time.strftime("%Y%m%d-%H%M%S", time.localtime(s.now())) + "-" + os.urandom(2).hex()
            try: ws, gd = prepare(s.repo, s.home, run)
            except Exception: return "PREFLIGHT:ARBEITSKOPIE"
            seen = st.get("seen", []); st.clear()
            st.update(seen=seen, run=run, ws=str(ws), gd=str(gd), branch="yolo/" + run, active=True, phase="IDLE", fails=0,
                      deadline=s.now() + c["max_seconds"], tasks_left=c["max_tasks"], steps_left=c["step_budget"],
                      refs=snap(s.repo), pins=fp(s.pins), desk=fp(s.desk))
            s.live.lines = []; s.live.freeze("BEREIT", run)
        s.ws, s.gd = Path(st["ws"]), Path(st["gd"])
        if not str(s.ws).startswith(str(s.home)): return "PREFLIGHT:WS_PFAD"
        if resume and s.real_bad(): return "PREFLIGHT:BASIS_GEAENDERT"
        st["hb"] = s.now(); s.save(); s.ready = True
        return ""

    def gate(s):
        if not s.ready and (err := s.begin()): return err
        st, c = s.s, s.c; st["hb"] = s.now()
        return ("NOTAUS" if s.stopped() else "LIMIT_ZEIT" if s.now() > st["deadline"] else
                "LIMIT_KONTINGENT" if st["tasks_left"] <= 0 or st["steps_left"] < c["steps"] else
                "SERIENFEHLER" if st["fails"] >= c["max_fails"] else "")

    def end(s, why):
        s.s.update(active=False); s.save(); s.live.freeze("GESTOPPT", "%s · %s" % (s.s.get("task", "-"), why))

    def next_task(s, known=()):
        """Datei-Modus: naechste tasks/*.md. Endlos-Modus (COURIER_YOLO_TASK_TEXT gesetzt): immer dieselbe 1-2-Satz-Aufgabe, Muse sucht den naechsten Ledger-Eintrag selbst."""
        if s.env.get("COURIER_YOLO_TASK_TEXT"):
            s.s["auto"] = s.s.get("auto", 0) + 1; s.save(); return "auto-%s-%04d" % (s.s["run"], s.s["auto"])
        for f in sorted(s.ws.glob(s.c["glob"])):
            if _ID.fullmatch(f.stem) and f.stem.lower() not in _SKIP and f.stem not in known and f.stem not in s.s["seen"]:
                s.s["seen"].append(f.stem); s.save(); return f.stem

    def command(s, pf):
        c = s.c
        cmd = [s.muse, "exec", "--json", "--provider", "meta", "--reasoning-effort", c["effort"], "--max-model-steps", str(c["steps"]),
               "--workspace", str(s.ws), "--prompt-file", str(pf), "--disable-approval",
               "--no-foreign-personal-context", "--no-session-log", "--disable-web-tools"]
        assert "--yolo" not in cmd and "--disable-sandbox" not in cmd
        return cmd

    def real_bad(s):
        st = s.s; bad = moved(s.repo, st["refs"])
        if bad:
            for r, v in bad.items(): git("update-ref", r, v, repo=s.repo, check=False)
            return "GUARD_REFS"
        return "GUARD_PIN" if fp(s.pins) != st["pins"] else "GUARD_DESKTOP" if fp(s.desk) != st["desk"] else ""

    def _wg(s, *a): return git(*a, gd=s.gd, wt=s.ws)

    def _finish(s, tid):
        st = s.s
        if st.get("phase") != "COMMITTED":
            s._wg("add", "-A"); s._wg("commit", "-q", "--allow-empty", "--no-verify", "-m", "Cannon " + tid, "-m", "Cannon-Task: " + tid)
            st.update(phase="COMMITTED", commit=s._wg("rev-parse", "HEAD")); s.save()
        bad = check_ws(s.gd, s.ws, st["before"]) or ("" if gitok("fetch", "-q", "--no-tags", str(s.gd), "refs/heads/{0}:refs/heads/{0}".format(st["branch"]), repo=s.repo) else "GUARD_HISTORY")
        if not bad: st.update(phase="INTEGRATED", fails=0); s.save()
        return bad

    def execute(s, tid):
        """-> (kind, detail, ergebnis|None); kind: done | failed | unknown."""
        st, c = s.s, s.c
        f = next((x for x in s.ws.glob(c["glob"]) if x.stem == tid), None)
        body = f.read_text(encoding="utf-8") if f else s.env.get("COURIER_YOLO_TASK_TEXT", "") if tid.startswith("auto-") else ""
        if not (body and _ID.fullmatch(tid)): return "unknown", "TASK_UNBEKANNT", None
        ph = st.get("phase", "IDLE"); act = ""
        if ph not in ("IDLE", "INTEGRATED"):
            alive = _alive(st.get("pid"))
            if alive and os.name != "nt":
                try: os.killpg(st["pid"], signal.SIGKILL)
                except OSError: pass
            act = recover(ph, st.get("task") == tid, s._wg("rev-parse", "HEAD"), not s._wg("status", "--porcelain"),
                          st.get("before"), st.get("commit"), alive)
            if act == "UNKNOWN": st["phase"] = "UNKNOWN"; s.live.freeze("UNKNOWN", tid + " · LEFTOVER"); return "unknown", "LEFTOVER", None
        res = None
        if act != "INTEGRATE":
            st.update(phase="CLAIMED", task=tid, before=s._wg("rev-parse", "HEAD")); s.save()
            pf = s.home / "prompts" / (tid + ".txt"); pf.parent.mkdir(parents=True, exist_ok=True)
            pf.write_text(build_prompt(tid, "Repo-Aufgabe " + tid, body, s.ws, st["branch"]), encoding="utf-8")
            s.live.start(tid); st["phase"] = "EXEC"; s.save()
            try: rc, parts, raw, why = run_muse(s.command(pf), str(s.ws), child_env(s.env), s.live, c["task_seconds"], c["idle_seconds"], s.stopped,
                                                lambda pid: (st.update(pid=pid), s.save()))
            except OSError: rc, parts, raw, why = 127, [], "", "START_FEHLER"
            st.pop("pid", None); st["steps_left"] -= c["steps"]; st["tasks_left"] -= 1
            variants = ["\n".join(parts), "".join(parts), raw]
            kind, detail = classify(rc, variants, raw, tid, why, s.real_bad())
            if kind == "unknown" and detail != "GUARD_REFS" and re.search(r"rate.?limit|quota|\b429\b|insufficient", raw[-2000:], re.I): detail += "+LIMIT_ANBIETER"
            res = parse(variants, tid)
            if kind == "failed": s._wg("reset", "-q", "--hard", st["before"]); s._wg("clean", "-q", "-fdx"); st.update(phase="IDLE", fails=st["fails"] + 1)
        else: kind, detail = "done", ""
        if kind == "done":
            bad = s._finish(tid)
            if bad: kind, detail = "unknown", bad
            elif res is not None: res["commit"] = st["commit"]
        if kind == "unknown": st["phase"] = "UNKNOWN"; s.live.freeze("UNKNOWN", "%s · %s" % (tid, detail))
        else: s.live.freeze("FERTIG" if kind == "done" else "FEHLER", "%s · %s" % (tid, detail or "ok"))
        s.save(); return kind, detail, res
