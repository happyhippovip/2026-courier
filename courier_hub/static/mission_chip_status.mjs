/** Paint the mission chip from the API body. A failed step is never PASS. */

export function chipStageView(data) {
  const checks = Array.isArray(data && data.checks) ? data.checks : [];
  const accepted = Boolean(data && data.verifier_result && data.verifier_result.accepted === true);
  const complete = Boolean(data && data.overall_status === "COMPLETE" && accepted);
  const labels = {
    1: ["✓ Bestanden (0,00 €)", "✗ Eingabe nicht bestanden"],
    2: ["✓ Artefakt erzeugt", "✗ Ausführung nicht bestanden"],
    3: ["✓ Verifiziert & im Ledger", "✗ Verifier nicht bestanden"],
  };
  const stages = [1, 2, 3].map((step) => {
    const check = checks.find((item) => item && item.step === step);
    const passed = complete && Boolean(check && check.passed === true && check.status === "PASS");
    return {
      step,
      className: passed ? "stage-box passed" : "stage-box failed",
      label: passed ? labels[step][0] : labels[step][1],
    };
  });
  return { complete, pill: complete ? "COMPLETE" : "FAILED", stages };
}
