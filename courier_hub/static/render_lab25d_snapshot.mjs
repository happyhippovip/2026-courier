/* Node-only static SVG render of the Lab (no browser needed).
 * Run: node courier_hub/static/render_lab25d_snapshot.mjs > /tmp/lab25d.svg
 * Honest label: static node render, NOT a browser screenshot.
 */
import { createLab } from "./kolibri_lab25d.mjs";

function makeNode(tag, ns) {
  const node = {
    tag,
    attrs: {},
    children: [],
    dataset: {},
    classList: { add() {} },
    textContent: "",
    setAttribute(k, v) {
      node.attrs[k] = String(v);
    },
    appendChild(c) {
      node.children.push(c);
      return c;
    },
  };
  return node;
}

function serialize(node) {
  const attrs = Object.entries(node.attrs)
    .map(([k, v]) => ` ${k}="${v}"`)
    .join("");
  const data = Object.entries(node.dataset)
    .map(([k, v]) => ` data-${k}="${v}"`)
    .join("");
  const inner = node.children.map(serialize).join("") + node.textContent;
  return `<${node.tag}${attrs}${data}>${inner}</${node.tag}>`;
}

globalThis.document = {
  createElementNS: (_ns, tag) => makeNode(tag),
  createElement: (tag) => {
    if (tag === "canvas") return { className: "", width: 0, height: 0, getContext: () => null };
    const n = makeNode(tag);
    return n;
  },
};
globalThis.window = { matchMedia: () => ({ matches: false }) };
globalThis.requestAnimationFrame = () => 0;
globalThis.cancelAnimationFrame = () => {};
globalThis.performance = { now: () => 0 };

const { mountLab } = await import("./kolibri_lab25d.mjs");
const lab = createLab({ mode: "demo" });
const chain = ["QUEUED", "READY", "RUNNING", "TRANSFERRED", "VERIFYING", "VERIFIED"];
chain.forEach((status, i) => lab.applyEvent({
  event_id: `snap-${i}`,
  workkey: "WK-DEMO-1",
  source: "A",
  target: status === "VERIFYING" || status === "VERIFIED" ? "C" : "B",
  status,
  timestamp: "2026-10-18T04:00:00Z",
}));
lab.applyEvent({ event_id: "snap-b", workkey: "WK-DEMO-2", status: "BLOCKED", timestamp: "t" });

const container = makeNode("div");
mountLab(container, lab, { reducedMotion: true });
const svg = container.children.find((c) => c.tag === "svg");
const banner = container.children.find((c) => c.tag === "p");
process.stdout.write(
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 460">\n<text x="16" y="28" fill="#fbbf24" font-size="14">${banner.textContent}</text>\n<g transform="translate(0,40)">${serialize(svg)}</g>\n</svg>\n`,
);
