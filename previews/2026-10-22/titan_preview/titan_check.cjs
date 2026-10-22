const { chromium } = require(process.env.PW);
const OUT = process.argv[2]; const BASE = "http://127.0.0.1:18777/titan/index.html";
const GREEN = /rgb\(16, 185, 129\)|#10b981/i;
(async () => {
  const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
  const res = []; const ok = (n, c, d = "") => res.push(`${c ? "PASS" : "FAIL"} ${n}${d ? " · " + d : ""}`);
  const p = await b.newPage({ viewport: { width: 1440, height: 1000 } });
  const errs = []; p.on("pageerror", (e) => errs.push(e.message)); p.on("console", (m) => m.type() === "error" && errs.push(m.text()));
  await p.goto(BASE); await p.waitForSelector("#universe svg");
  // REPLAY: verified project with badge
  const banner = await p.textContent("#mode-banner"); ok("REPLAY banner", banner.startsWith("REPLAY"), banner.slice(0, 70));
  const proj = await p.$$eval("#universe .universe-project", (gs) => gs.map((g) => g.getAttribute("aria-label")));
  ok("REPLAY Projekte aus echtem Lauf", proj.length >= 3, proj.join(" | "));
  const vid = await p.$$eval("#universe .universe-project", (gs) => (gs.find((g) => /VERIFIED/.test(g.getAttribute("aria-label"))) || {}).getAttribute?.("data-workkey"));
  await p.click(`#universe [data-workkey="${vid}"]`, { force: true });
  const det = await p.textContent("#detail"); ok("Detailkarte verified", /VERIFIED/.test(det) && /journal:\d+:RESULT_ACCEPTED/.test(det), det.replace(/\s+/g, " ").slice(0, 120));
  const badge = await p.getAttribute("#detail .evidence-badge", "data-state"); ok("Badge VERIFIED (Hub-Anker)", badge === "VERIFIED", badge);
  await p.screenshot({ path: `${OUT}/1440_replay_verified.png`, fullPage: true });
  const uid = await p.$$eval("#universe .universe-project", (gs) => (gs.find((g) => /UNKNOWN/.test(g.getAttribute("aria-label"))) || {}).getAttribute?.("data-workkey"));
  if (uid) { await p.click(`#universe [data-workkey="${uid}"]`, { force: true }); const b2 = await p.getAttribute("#detail .evidence-badge", "data-state"); ok("Gescheiterter Lauf nicht grün", b2 !== "VERIFIED", b2); }
  // Filter
  await p.uncheck("#f-VERIFIED"); const hid = await p.$$eval("#universe .titan-hidden", (x) => x.length); ok("Filter VERIFIED aus", hid >= 1, `${hid} versteckt`); await p.check("#f-VERIFIED");
  // Keyboard path
  await p.focus(`#universe [data-workkey="${vid}"]`); await p.keyboard.press("Enter"); ok("Tastatur Enter", /Projekt/.test(await p.textContent("#detail")));
  // Beams
  ok("Beams-Canvas vorhanden", Boolean(await p.$("#beams")));
  // DEMO
  await p.selectOption("#mode", "demo"); await p.waitForFunction(() => document.querySelector("#mode-banner").textContent.startsWith("DEMO"));
  const agents = await p.$$eval("#universe .universe-agent", (gs) => gs.map((g) => g.getAttribute("data-workkey")));
  ok("DEMO Agenten/Teamplaneten", agents.length >= 1, agents.join(","));
  await p.click(`#universe [data-workkey="${agents[0]}"]`, { force: true }); const dd = await p.textContent("#detail");
  ok("DEMO Detail Owner/Workkey/Lease", /demo-agent/.test(dd) && /DEMO-001/.test(dd) && /DEMO-LEASE/.test(dd));
  const greens = await p.$$eval("#universe [fill],#universe [stroke]", (els) => els.filter((e) => /#10b981/i.test(e.getAttribute("fill") || "") || /#10b981/i.test(e.getAttribute("stroke") || "")).length);
  ok("DEMO nie grün", greens === 0, `${greens} grüne Elemente`);
  await p.screenshot({ path: `${OUT}/1440_demo_detail.png`, fullPage: true });
  // LIVE (no hub running) -> UNKNOWN
  await p.selectOption("#mode", "live"); await p.waitForFunction(() => /UNKNOWN/.test(document.querySelector("#mode-banner").textContent));
  ok("LIVE ohne Hub = UNKNOWN", true, await p.textContent("#mode-banner"));
  await p.screenshot({ path: `${OUT}/1440_live_unknown.png`, fullPage: true });
  // Motion toggle
  await p.click("#motion"); ok("Bewegung anhalten", (await p.getAttribute("#motion", "aria-pressed")) === "true");
  // Mobile + reduced motion
  const m = await b.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: "reduce" });
  await m.goto(BASE); await m.waitForSelector("#universe svg");
  ok("390px reduced-motion: pausiert", (await m.getAttribute("#motion", "aria-pressed")) === "true");
  const sw = await m.evaluate(() => document.documentElement.scrollWidth); ok("390px kein horizontales Scrollen", sw <= 392, `scrollWidth ${sw}`);
  await m.screenshot({ path: `${OUT}/390_replay_reduced.png`, fullPage: true });
  ok("Keine JS-Fehler", errs.length === 0, errs.join(" | ").slice(0, 200));
  console.log(res.join("\n")); await b.close();
})().catch((e) => { console.error(e); process.exit(1); });
