// Goal-draft rules for the Magic Composer. No execution, no uploads.

export const GOAL_MAX = 4000;
export const FILE_MAX = 12;

export const COPY = {
  title: "Was soll Courier für dich tun?",
  lead: "Ein Satz genügt. Datei und Sprache nur auf Wunsch.",
  placeholder: "Erstelle mir einen Bericht aus diesen Dateien.",
  file: "Datei",
  voice: "Sprache",
  voiceStop: "Stopp",
  reviewButton: "Auftrag prüfen",
  sendButton: "Absenden",
  back: "Zurück",
  copy: "Kopieren",
  copied: "Kopiert",
  again: "Neuen Auftrag",
  allow: "Erlauben",
  notNow: "Nicht jetzt",
  executionLabel: "Ausführung",
  permissionLabel: "Berechtigung",
  keyLabel: "Taste",
  emptyGoal: "Schreib zuerst, was Courier tun soll.",
  tooLong: "Der Auftrag ist zu lang. Kürze ihn auf 4000 Zeichen.",
  fileLimit: "Höchstens 12 Dateien. Weitere wurden nicht übernommen.",
  executionCompose: "Absenden vergibt eine Task-ID. Die Ausführung beginnt nach deiner Freigabe.",
  executionReview: "Absenden vergibt eine Task-ID. Die Ausführung wartet danach auf deine Freigabe.",
  executionReceipt: "Ausführung wartet auf deine Freigabe.",
  permissionIdle: "Datei und Mikrofon bleiben geschlossen, bis du sie hier öffnest. Übernommen werden dein Text und die Dateinamen.",
  permissionFiles: "Die ausgewählten Dateien stehen nur mit ihrem Namen hier. Kein Upload. Das Mikrofon bleibt zu, bis du Sprache öffnest.",
  permissionAsk: "Mikrofon nur für diese Eingabe. Der Text bleibt hier, bis du absendest.",
  permissionListening: "Mikrofon ist an, nur für diese Eingabe. Stopp beendet die Aufnahme.",
  permissionDenied: "Mikrofon nicht erlaubt. Tippen und Datei bleiben offen.",
  permissionUnsupported: "Sprache ist in diesem Browser nicht verfügbar. Tippen und Datei bleiben offen.",
  voiceNetwork: "Sprache ist gerade nicht erreichbar. Tippen bleibt offen.",
  voiceUsed: "In den Text übernommen.",
  voiceUnused: "Nicht verwendet.",
  noFiles: "Keine Datei ausgewählt.",
  reviewExecution: "Es entsteht eine Task-ID. Die Ausführung wartet auf deine Freigabe.",
  reviewPermissionFiles: "Nur die Namen der ausgewählten Dateien. Kein Upload.",
  reviewPermissionNoFiles: "Keine Datei geöffnet.",
  reviewPermissionVoice: "Mikrofon war nur für die Eingabe an.",
  reviewPermissionNoVoice: "Mikrofon blieb geschlossen.",
  receiptTitle: "Auftrag bereit",
  reviewTitle: "Auftrag prüfen",
  keyHint: "Strg + Enter oder Befehl + Enter geht den nächsten Schritt.",
  receiptNote: "Die Task-ID gehört zu diesem Auftrag.",
  drop: "Dateien loslassen, um sie aufzunehmen.",
  removeLabel: "entfernen",
};

export const PATH_STEPS = [
  { id: "type", label: "Tippen" },
  { id: "file", label: "Datei", optional: true },
  { id: "voice", label: "Sprache", optional: true },
  { id: "review", label: "Prüfen" },
  { id: "send", label: "Absenden" },
  { id: "task", label: "Task-ID" },
];

export function normalizeGoal(text) {
  return String(text ?? "").trim();
}

export function goalBlockReason(text) {
  const goal = normalizeGoal(text);
  if (!goal) return COPY.emptyGoal;
  if (goal.length > GOAL_MAX) return COPY.tooLong;
  return "";
}

export function canReview(text) {
  return goalBlockReason(text) === "";
}

export function formatBytes(size) {
  const n = Math.max(0, Number(size) || 0);
  if (n < 1024) return `${Math.round(n)} B`;
  if (n < 1024 * 1024) return `${Math.max(1, Math.round(n / 1024))} KB`;
  const mb = n / (1024 * 1024);
  return `${mb >= 10 ? Math.round(mb) : mb.toFixed(1)} MB`;
}

export function addFiles(existing, incoming, max = FILE_MAX) {
  const files = existing.map((file) => ({
    name: String(file.name || "datei"),
    size: Math.max(0, Number(file.size) || 0),
    type: String(file.type || ""),
  }));
  let overflow = false;
  for (const file of incoming) {
    if (files.length >= max) {
      overflow = true;
      break;
    }
    files.push({
      name: String(file.name || "datei"),
      size: Math.max(0, Number(file.size) || 0),
      type: String(file.type || ""),
    });
  }
  return { files, overflow };
}

export function createTaskId(randomBytes) {
  const bytes = randomBytes ?? crypto.getRandomValues(new Uint8Array(16));
  if (!bytes || bytes.length < 16) throw new Error("task id needs 16 bytes");
  let hex = "";
  for (let i = 0; i < 16; i += 1) hex += Number(bytes[i]).toString(16).padStart(2, "0");
  return `task-${hex}`;
}

export function fileSummary(files) {
  if (!files.length) return COPY.noFiles;
  return files.map((file) => `${file.name} (${formatBytes(file.size)})`).join(", ");
}

export function voiceSummary(voiceUsed) {
  return voiceUsed ? COPY.voiceUsed : COPY.voiceUnused;
}

export function reviewPermission(files, voiceUsed) {
  const fileLine = files.length ? COPY.reviewPermissionFiles : COPY.reviewPermissionNoFiles;
  const voiceLine = voiceUsed ? COPY.reviewPermissionVoice : COPY.reviewPermissionNoVoice;
  return `${fileLine} ${voiceLine}`;
}

export function buildReview(draft) {
  return {
    goal: normalizeGoal(draft.text),
    files: fileSummary(draft.files),
    voice: voiceSummary(draft.voiceUsed),
    execution: COPY.reviewExecution,
    permission: reviewPermission(draft.files, draft.voiceUsed),
  };
}

export function executionHint(phase) {
  if (phase === "review") return COPY.executionReview;
  if (phase === "receipt") return COPY.executionReceipt;
  return COPY.executionCompose;
}

export function permissionHint({ files = [], voice = "idle" } = {}) {
  if (voice === "ask") return COPY.permissionAsk;
  if (voice === "listening") return COPY.permissionListening;
  if (voice === "denied") return COPY.permissionDenied;
  if (voice === "unsupported") return COPY.permissionUnsupported;
  if (files.length) return COPY.permissionFiles;
  return COPY.permissionIdle;
}

export function pathMarks({ phase = "compose", text = "", files = [], voiceUsed = false } = {}) {
  const hasText = normalizeGoal(text).length > 0;
  const current = phase === "receipt" ? "task" : phase === "review" ? "review" : "type";
  return PATH_STEPS.map((step) => ({
    id: step.id,
    label: step.label,
    optional: Boolean(step.optional),
    current: step.id === current,
    done: (step.id === "type" && (hasText || phase !== "compose"))
      || (step.id === "file" && files.length > 0)
      || (step.id === "voice" && Boolean(voiceUsed))
      || (step.id === "review" && (phase === "review" || phase === "receipt"))
      || (step.id === "send" && phase === "receipt")
      || (step.id === "task" && phase === "receipt"),
    next: (phase === "compose" && hasText && step.id === "review")
      || (phase === "review" && step.id === "send"),
  }));
}
