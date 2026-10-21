// Kolibri bioluminescent background (V101 draft, isolated). Canvas 2D.
// Painted once per resize from a fixed seed (deterministic), no render loop:
// the slow organic drift is a CSS transform on the canvas (see BIOSPHERE_CSS),
// which the compositor runs and which stops under prefers-reduced-motion.
// Colours are ambient light with no meaning. The verified green (#10b981) is
// never used here, so the background can never look like a verified result.

export const BIOSPHERE_LIMITS = Object.freeze({ clusters: 9, glyphs: 40, dpr: 1.5 });
export const BIOSPHERE_COLORS = Object.freeze({
  teal: "#14b8a6", violet: "#7c3aed", blue: "#2563eb", moss: "#2f5d3a", magenta: "#be185d", gold: "#b08d3c",
});
const GLYPHS = "01ケサタナハマヤラワ∞";

export const BIOSPHERE_CSS = `
#biosphere { position: fixed; inset: -4%; width: 108%; height: 108%; z-index: -2; pointer-events: none;
  animation: kolibri-biosphere-drift 90s ease-in-out infinite alternate; }
@keyframes kolibri-biosphere-drift { from { transform: translate3d(0,0,0) scale(1); }
  to { transform: translate3d(-1.5%, 1%, 0) scale(1.03); } }
@media (prefers-reduced-motion: reduce) { #biosphere { animation: none; } }`;

/** mulberry32: small deterministic PRNG, so the same seed paints the same picture. */
export function prng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Paint the background once. Returns what was drawn (for tests and budgets). */
export function paintBiosphere(canvas, { width, height, dpr = 1, seed = 20261019 } = {}) {
  const scale = Math.min(dpr, BIOSPHERE_LIMITS.dpr);
  canvas.width = Math.floor(width * scale);
  canvas.height = Math.floor(height * scale);
  const ctx = canvas.getContext("2d");
  const rand = prng(seed);
  const palette = Object.values(BIOSPHERE_COLORS);
  ctx.setTransform(scale, 0, 0, scale, 0, 0);

  const depth = ctx.createLinearGradient(0, 0, 0, height);
  depth.addColorStop(0, "#020208");
  depth.addColorStop(1, "#05030c");
  ctx.fillStyle = depth;
  ctx.fillRect(0, 0, width, height);

  ctx.globalCompositeOperation = "lighter";
  const clusters = [];
  for (let i = 0; i < BIOSPHERE_LIMITS.clusters; i += 1) {
    const x = rand() * width;
    const y = rand() * height;
    const r = (0.12 + rand() * 0.18) * Math.max(width, height);
    const color = palette[i % palette.length];
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, color);
    g.addColorStop(1, "rgba(0,0,0,0)");
    ctx.globalAlpha = 0.12 + rand() * 0.06;
    ctx.fillStyle = g;
    ctx.fillRect(x - r, y - r, r * 2, r * 2);
    for (let cell = 0; cell < 5; cell += 1) { // small cells inside the cluster
      const cx = x + (rand() - 0.5) * r;
      const cy = y + (rand() - 0.5) * r;
      ctx.globalAlpha = 0.09;
      ctx.beginPath(); ctx.arc(cx, cy, 6 + rand() * 18, 0, Math.PI * 2); ctx.fill();
    }
    clusters.push({ x, y, r, color });
  }

  ctx.globalCompositeOperation = "source-over";
  ctx.font = "12px ui-monospace, monospace";
  const glyphs = [];
  for (let i = 0; i < BIOSPHERE_LIMITS.glyphs; i += 1) {
    const ch = GLYPHS[Math.floor(rand() * GLYPHS.length)];
    const x = rand() * width;
    const y = rand() * height;
    ctx.globalAlpha = 0.10;
    ctx.fillStyle = BIOSPHERE_COLORS.teal;
    ctx.fillText(ch, x, y);
    glyphs.push({ ch, x, y });
  }
  ctx.globalAlpha = 1;
  return { clusters, glyphs, colors: palette };
}
