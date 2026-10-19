// Kolibri particle field (Signal Lab V17 slice). One calm 2D drift behind the
// dashboard: capped count, no polling, pauses when the tab is hidden, fully
// off under prefers-reduced-motion. No 3D here (optional elsewhere, never
// default). The caller owns one initParticles() per page load.

export const PARTICLE_MAX = 64;
export const PARTICLE_COLORS = ["#06b6d4", "#ec4899", "#a855f7"];

function makeDots(width, height, count) {
  const dots = [];
  for (let i = 0; i < count; i += 1) {
    dots.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.12,
      vy: (Math.random() - 0.5) * 0.12,
      r: 0.8 + Math.random() * 1.6,
      c: PARTICLE_COLORS[i % PARTICLE_COLORS.length],
      a: 0.25 + Math.random() * 0.4,
    });
  }
  return dots;
}

export function initParticles(canvas) {
  if (!canvas || typeof canvas.getContext !== "function") return { destroy() {} };
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return { destroy() {} };
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) return { destroy() {} };
  const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
  let dots = [];
  let frame = 0;
  let alive = true;

  function resize() {
    canvas.width = Math.floor(window.innerWidth * dpr);
    canvas.height = Math.floor(window.innerHeight * dpr);
    const count = window.innerWidth < 760 ? PARTICLE_MAX / 2 : PARTICLE_MAX;
    dots = makeDots(canvas.width / dpr, canvas.height / dpr, count);
  }

  function tick() {
    if (!alive) return;
    if (!document.hidden) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.save();
      ctx.scale(dpr, dpr);
      for (const d of dots) {
        d.x += d.vx;
        d.y += d.vy;
        const w = canvas.width / dpr;
        const h = canvas.height / dpr;
        if (d.x < 0) d.x = w;
        if (d.x > w) d.x = 0;
        if (d.y < 0) d.y = h;
        if (d.y > h) d.y = 0;
        ctx.globalAlpha = d.a;
        ctx.fillStyle = d.c;
        ctx.beginPath();
        ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
    frame = window.requestAnimationFrame(tick);
  }

  function onVis() {
    if (!document.hidden && alive && !frame) frame = window.requestAnimationFrame(tick);
  }

  window.addEventListener("resize", resize);
  document.addEventListener("visibilitychange", onVis);
  resize();
  frame = window.requestAnimationFrame(tick);
  return {
    destroy() {
      alive = false;
      window.cancelAnimationFrame(frame);
      frame = 0;
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", onVis);
    },
  };
}
