// What the Mission Chip screens may claim. The server already says when a run
// is only a local demo. The screen must not paint a stronger label than that.

export const GOLD_RESOLUTION = "BYTE_LEVEL_GOLD_VERIFIED";

export function presentMissionChip(data) {
  const body = data && typeof data === "object" ? data : {};
  const verdict = body.verifier_result && typeof body.verifier_result === "object"
    ? body.verifier_result
    : {};
  const resolution = typeof verdict.resolution === "string" && verdict.resolution
    ? verdict.resolution
    : "UNKNOWN";
  const mode = typeof body.mode === "string" ? body.mode : "";
  const demo = body.product_ready !== true || mode.startsWith("DEMO");
  const accepted = body.overall_status === "COMPLETE" && verdict.accepted === true;
  const gold = demo === false && accepted === true && resolution === GOLD_RESOLUTION;
  let costLabel = "Kosten unbekannt";
  if (typeof body.cost_eur === "number" && Number.isFinite(body.cost_eur)) {
    costLabel = `${body.cost_eur.toFixed(2).replace(".", ",")} €`;
  }
  return {
    demo,
    gold,
    accepted,
    resolution,
    costLabel,
    stage1: demo ? `DEMO · ${costLabel}` : (accepted ? `✓ OK (${costLabel})` : "Nicht bestätigt"),
    stage2: accepted ? "✓ Artefakt erzeugt" : "Artefakt nicht bestätigt",
    stage3: gold
      ? "✓ BYTE_LEVEL_GOLD_VERIFIED"
      : (demo ? "DEMO — nicht produktverifiziert" : resolution),
    laneVerified: gold,
    laneDone: gold,
  };
}
