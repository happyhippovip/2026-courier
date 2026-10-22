import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";
import { presentMissionChip } from "../../courier_hub/static/mission_chip_truth.mjs";

const DEMO_RUN = {
  mode: "DEMO / LOKAL DETERMINISTISCH",
  product_ready: false,
  overall_status: "COMPLETE",
  cost_eur: 0,
  verifier_result: { accepted: true, resolution: "verified" },
};

test("a local demo run is not painted as byte-level gold", () => {
  const view = presentMissionChip(DEMO_RUN);
  assert.equal(view.demo, true);
  assert.equal(view.gold, false);
  assert.equal(view.laneVerified, false);
  assert.equal(view.laneDone, false);
  assert.equal(view.stage3, "DEMO — nicht produktverifiziert");
  assert.equal(view.resolution, "verified");
  assert.doesNotMatch(view.stage3, /BYTE_LEVEL_GOLD_VERIFIED/);
});

test("gold is shown only for an exact product resolution", () => {
  const view = presentMissionChip({
    mode: "PRODUCT",
    product_ready: true,
    overall_status: "COMPLETE",
    cost_eur: 0,
    verifier_result: { accepted: true, resolution: "BYTE_LEVEL_GOLD_VERIFIED" },
  });
  assert.equal(view.gold, true);
  assert.equal(view.stage3, "✓ BYTE_LEVEL_GOLD_VERIFIED");
});

test("a product run whose resolution is only verified stays at that word", () => {
  const view = presentMissionChip({
    mode: "PRODUCT",
    product_ready: true,
    overall_status: "COMPLETE",
    cost_eur: 0,
    verifier_result: { accepted: true, resolution: "verified" },
  });
  assert.equal(view.gold, false);
  assert.equal(view.stage3, "verified");
});

test("missing cost is not shown as zero", () => {
  const view = presentMissionChip({
    mode: "PRODUCT",
    product_ready: true,
    overall_status: "FAILED",
    verifier_result: { accepted: false, resolution: "rejected" },
  });
  assert.equal(view.costLabel, "Kosten unbekannt");
  assert.equal(view.gold, false);
});

test("the Kolibri button uses the shared verdict and does not append a gold label", () => {
  const src = fs.readFileSync(new URL("../../courier_hub/static/kolibri.js", import.meta.url), "utf8");
  assert.match(src, /presentMissionChip/);
  assert.doesNotMatch(src, /BYTE_LEVEL_GOLD_VERIFIED\)/);
});
