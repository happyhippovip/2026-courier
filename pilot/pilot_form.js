function missingPilotFields(goalText, apiKey) {
  const missing = [];
  if (!String(goalText || "").trim()) {
    missing.push({ id: "goal-text", name: "what you want to do" });
  }
  if (!String(apiKey || "").trim()) {
    missing.push({ id: "api-key", name: "the connection API key" });
  }
  return missing;
}

function pilotFieldError(missing) {
  if (!missing.length) return "";
  const names = missing.map((field) => field.name);
  const listed = names.length === 1
    ? names[0]
    : names.slice(0, -1).join(", ") + " and " + names[names.length - 1];
  return "Courier did not start. Enter " + listed + ".";
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { missingPilotFields, pilotFieldError };
}
