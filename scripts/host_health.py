#!/usr/bin/env python3
"""Host health check: why is this computer slow? (Windows + macOS + Linux)

Read-only. Measures memory, CPU, disk, uptime, which programs use the most
memory (grouped by program, counting instances) and what starts automatically,
then says in plain words what is wrong and what to do. It never closes,
kills or changes anything.

Usage: python scripts/host_health.py [--json report.json]
"""
import json
import os
import sys
import time
from pathlib import Path

GB = 1024 ** 3


def _startup_items():
    """Programs that start automatically. Unknown on a platform -> empty, not guessed."""
    items = []
    if sys.platform == "win32":
        try:
            import winreg
            for hive, label in ((winreg.HKEY_CURRENT_USER, "HKCU"), (winreg.HKEY_LOCAL_MACHINE, "HKLM")):
                try:
                    key = winreg.OpenKey(hive, r"Software\Microsoft\Windows\CurrentVersion\Run")
                except OSError:
                    continue
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    items.append({"name": name, "where": f"{label} Run", "command": str(value)[:160]})
                    i += 1
        except ImportError:
            pass
        folder = Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup"
        items += [{"name": p.stem, "where": "Startup folder", "command": p.name} for p in folder.glob("*")
                  if p.is_file()]
    elif sys.platform == "darwin":
        for folder in (Path.home() / "Library/LaunchAgents", Path("/Library/LaunchAgents")):
            items += [{"name": p.stem, "where": str(folder), "command": p.name} for p in folder.glob("*.plist")]
    return items


def snapshot():
    import psutil
    vm, sw = psutil.virtual_memory(), psutil.swap_memory()
    groups = {}
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            name = (p.info["name"] or "?").lower().removesuffix(".exe")
            rss = p.info["memory_info"].rss if p.info["memory_info"] else 0
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        g = groups.setdefault(name, {"name": name, "count": 0, "rss_gb": 0.0})
        g["count"] += 1
        g["rss_gb"] += rss / GB
    root = "C:\\" if sys.platform == "win32" else "/"
    du = psutil.disk_usage(root)
    return {
        "platform": sys.platform, "taken_at": time.time(),
        "uptime_min": round((time.time() - psutil.boot_time()) / 60, 1),
        "ram_total_gb": round(vm.total / GB, 1), "ram_used_pct": vm.percent,
        "swap_used_pct": sw.percent, "cpu_pct": psutil.cpu_percent(interval=1.0),
        "disk_free_pct": round(100 - du.percent, 1), "process_count": len(psutil.pids()),
        "groups": sorted(({**g, "rss_gb": round(g["rss_gb"], 2)} for g in groups.values()),
                         key=lambda g: -g["rss_gb"])[:15],
        "startup": _startup_items(),
    }


AI_TOOLS = ("antigravity", "claude", "chatgpt", "cursor", "code", "language_server", "muse", "codex", "ollama")
UPDATE_TOOLS = ("tiworker", "trustedinstaller", "msmpeng", "searchindexer", "onedrive", "wuauclt", "softwareupdate")


def diagnose(s):
    """Plain-language findings, most important first. Pure function (testable)."""
    found = []
    ram, total = s["ram_used_pct"], s["ram_total_gb"]
    if ram >= 90:
        found.append(("high", f"Arbeitsspeicher fast voll ({ram:.0f} % von {total} GB). Das macht den Computer zäh."))
    elif ram >= 80:
        found.append(("medium", f"Arbeitsspeicher knapp ({ram:.0f} % von {total} GB)."))
    for g in s["groups"][:5]:
        share = 100 * g["rss_gb"] / total if total else 0
        if share >= 20 or g["count"] >= 10:
            what = f"{g['name']}: {g['rss_gb']} GB in {g['count']} Prozessen"
            tip = ("Fenster dieses Programms auf 1–2 begrenzen oder ganz schließen, wenn nicht gebraucht."
                   if any(t in g["name"] for t in AI_TOOLS) else "Prüfen, ob es gerade gebraucht wird.")
            found.append(("high" if share >= 20 else "medium", f"{what}. {tip}"))
    busy_updates = [g["name"] for g in s["groups"] if any(u in g["name"] for u in UPDATE_TOOLS)]
    if s["uptime_min"] < 30:
        msg = f"Der Computer läuft erst seit {s['uptime_min']:.0f} Minuten."
        if busy_updates:
            msg += (f" Gerade arbeiten Windows-Update/Virenschutz/Suche ({', '.join(busy_updates)}). "
                    "Das ist nach einem Neustart normal und geht meist in 10–30 Minuten vorbei – nicht abbrechen.")
        if s["startup"]:
            msg += f" Automatisch gestartet werden {len(s['startup'])} Programme – siehe Liste."
        found.append(("medium" if (busy_updates or len(s["startup"]) > 8) else "low", msg))
    if len(s["startup"]) > 8:
        found.append(("medium", f"{len(s['startup'])} Programme starten automatisch. Unnötige im Autostart "
                                "abschalten (Windows: Task-Manager → Autostart; Mac: Einstellungen → Anmeldeobjekte)."))
    if s["swap_used_pct"] >= 50 and ram >= 80:
        found.append(("high", "Der Computer lagert viel auf die Festplatte aus – deshalb hängt er."))
    if s["disk_free_pct"] < 10:
        found.append(("high", f"Nur noch {s['disk_free_pct']} % Speicherplatz frei. Dateien aufräumen."))
    if s["cpu_pct"] >= 90:
        found.append(("medium", f"Prozessor voll ausgelastet ({s['cpu_pct']:.0f} %)."))
    if not found:
        found.append(("ok", "Keine Auffälligkeit gemessen. Wenn es trotzdem hängt: Messung wiederholen, während es hängt."))
    order = {"high": 0, "medium": 1, "low": 2, "ok": 3}
    return sorted(found, key=lambda f: order[f[0]])


def render(s, findings):
    lines = [f"Computer-Check ({s['platform']}), läuft seit {s['uptime_min']:.0f} min",
             f"RAM {s['ram_used_pct']:.0f} % von {s['ram_total_gb']} GB · Auslagerung {s['swap_used_pct']:.0f} % · "
             f"CPU {s['cpu_pct']:.0f} % · Platte frei {s['disk_free_pct']} % · {s['process_count']} Prozesse", "",
             "BEFUND:"]
    lines += [f"  [{sev}] {msg}" for sev, msg in findings]
    lines += ["", "GRÖSSTE PROGRAMME:"]
    lines += [f"  {g['rss_gb']:>6} GB  {g['count']:>3}x  {g['name']}" for g in s["groups"][:10]]
    if s["startup"]:
        lines += ["", "AUTOSTART:"] + [f"  {i['name']}  ({i['where']})" for i in s["startup"][:25]]
    lines += ["", "Hinweis: Dieser Check liest nur. Er schließt und ändert nichts."]
    return "\n".join(lines)


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    try:
        s = snapshot()
    except ImportError:
        print("Host-Check braucht das Paket 'psutil' (pip install psutil).")
        return 2
    findings = diagnose(s)
    print(render(s, findings))
    if len(argv) == 2 and argv[0] == "--json":
        Path(argv[1]).write_text(json.dumps({"snapshot": s, "findings": findings}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
