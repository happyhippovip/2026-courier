"""Browser smoke for the Desktop Hub (lane L5), run by hand, not by CI.

    pip install playwright          # not a repository dependency
    python tests/hub/browser_smoke.py [--chromium <path to chrome>]

It starts the real controller service and the hub in-process, gives them real
runtime states (checked, blocked, running, stopped after a one-shot action
started), then drives a real Chromium with the keyboard only:

1. Home loads with the three piles and no console errors.
2. Every action is reachable with Tab; a Needs-you decision can take focus.
3. The Working card shows its observable state.
4. A Done receipt opens with Enter, answers "How Courier knows", saves its
   support record as a file, and Escape returns focus to the card.
5. The stopped-after-start card says the action may already have happened.
6. "It happened", chosen with the keyboard, moves the item to Done as
   confirmed by the person, without the check mark.

Exit status 0 means every step held.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "controller"), str(HERE.parents[1])]

from ctrl_helpers import FakeClock, LiveService, task_body  # noqa: E402
from test_hub_product import HubProcess, blocked_task, verified_task  # noqa: E402


def build_world(home: Path):
    clock = FakeClock()
    live = LiveService(home, clock=clock)
    hub = HubProcess(home, live.base)
    verified_task(live)
    stopped = live.post("/v1/tasks", task_body(effect_class="non_idempotent")).json()["task_id"]
    lease = live.post("/v1/claim", {"worker_id": "w-stop"}).json()
    live.post("/v1/start", {"dispatch_id": lease["dispatch_id"]})
    live.post(f"/v1/tasks/{stopped}/cancel", {"actor": "desktop:tester", "reason": "smoke"})
    live.post("/v1/heartbeat", {"worker_id": "w-stop", "dispatch_ids": []})  # the worker confirms the stop
    blocked = blocked_task(live, clock)
    running = live.post("/v1/tasks", task_body()).json()["task_id"]
    lease = live.post("/v1/claim", {"worker_id": "w-run"}).json()
    live.post("/v1/start", {"dispatch_id": lease["dispatch_id"]})
    return live, hub, {"blocked": blocked, "running": running, "stopped": stopped}


def tab_until(page, predicate, limit=60):
    for _ in range(limit):
        page.keyboard.press("Tab")
        if page.evaluate(predicate):
            return True
    return False


def run(chromium: str | None) -> list:
    from playwright.sync_api import sync_playwright
    failures = []

    def check(ok, what):
        print(("ok   " if ok else "FAIL ") + what)
        if not ok:
            failures.append(what)

    with tempfile.TemporaryDirectory() as tmp:
        live, hub, ids = build_world(Path(tmp) / "home")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(**({"executable_path": chromium} if chromium else {}))
                page = browser.new_page()
                errors = []
                page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(hub.base + "/")
                page.wait_for_selector(".card")

                piles = page.eval_on_selector_all("main section.pile", "els => els.map(e => e.classList[1])")
                check(piles == ["pile-needs_you", "pile-working", "pile-done"], f"three piles in order {piles}")

                actions = page.eval_on_selector_all("[data-action]", "els => els.length")
                reached = set()
                page.focus("body")
                for _ in range(actions + 10):
                    page.keyboard.press("Tab")
                    key = page.evaluate("document.activeElement?.dataset?.action ? "
                                        "document.activeElement.dataset.id + '/' + document.activeElement.textContent"
                                        " : null")
                    if key:
                        reached.add(key)
                check(len(reached) == actions, f"every action reachable with Tab ({len(reached)}/{actions})")

                page.focus("body")
                check(tab_until(page, "document.activeElement?.dataset?.decision === 'effect_confirmed'"),
                      "a Needs-you decision takes keyboard focus")

                working = page.inner_text(f"article[data-id='{ids['running']}']")
                check("In progress" in working, "Working card shows In progress")

                stopped = page.inner_text(f"article[data-id='{ids['stopped']}']")
                check("may already have happened" in stopped, "stop after start says it may have happened")

                page.focus("body")
                check(tab_until(page, "document.activeElement?.dataset?.action === 'details' && "
                                      "document.activeElement.closest('.outcome-verified') !== null"),
                      "Done receipt button reachable with Tab")
                page.keyboard.press("Enter")
                page.wait_for_selector(".receipt")
                receipt = page.inner_text("#detail-body")
                check("How Courier knows" in receipt and "Checked by Courier" in receipt, "receipt answers how")
                page.click("#detail-body summary")  # support data stays folded away until asked for
                with page.expect_download() as saved:
                    page.click("text=Save support record")
                record = json.loads(Path(saved.value.path()).read_text(encoding="utf-8"))
                check(record.get("kind") == "courier.support_export", "support record saves as a file")
                page.focus("#detail-close")
                page.keyboard.press("Escape")
                check(page.evaluate("document.activeElement?.dataset?.action === 'details'"),
                      "Escape returns focus to the card")

                page.focus("body")
                tab_until(page, "document.activeElement?.dataset?.decision === 'effect_confirmed'")
                page.keyboard.press("Enter")
                page.wait_for_selector(f"article.outcome-human_confirmed[data-id='{ids['blocked']}']", timeout=15000)
                card = page.inner_text(f"article[data-id='{ids['blocked']}']")
                check("Confirmed by" in card and "✓" not in card, "It happened -> Done, confirmed, no check mark")
                check(page.inner_text("#toast") == "Recorded.", "the decision is announced")
                check(not errors, f"no console errors {errors}")
                browser.close()
        finally:
            hub.stop()
            live.stop()
    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chromium", default=None, help="Chromium executable (default: Playwright's own)")
    failures = run(parser.parse_args().chromium)
    print("BROWSER SMOKE:", "PASS" if not failures else f"FAIL ({len(failures)})")
    sys.exit(1 if failures else 0)
