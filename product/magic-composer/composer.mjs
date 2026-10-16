import {
  COPY,
  addFiles,
  buildReview,
  canReview,
  createTaskId,
  executionHint,
  formatBytes,
  goalBlockReason,
  pathMarks,
  permissionHint,
} from "./model.mjs";

const els = {
  stage: document.querySelector("#stage"),
  field: document.querySelector("#field"),
  goal: document.querySelector("#goal"),
  fileButton: document.querySelector("#file-button"),
  fileInput: document.querySelector("#file-input"),
  chips: document.querySelector("#chips"),
  voiceButton: document.querySelector("#voice-button"),
  voiceLabel: document.querySelector("#voice-label"),
  voiceAsk: document.querySelector("#voice-ask"),
  voiceAllow: document.querySelector("#voice-allow"),
  voiceDecline: document.querySelector("#voice-decline"),
  voiceCaption: document.querySelector("#voice-caption"),
  reviewButton: document.querySelector("#review-button"),
  dropNote: document.querySelector("#drop-note"),
  compose: document.querySelector("#compose"),
  review: document.querySelector("#review"),
  reviewHeading: document.querySelector("#review-heading"),
  quote: document.querySelector("#goal-quote"),
  reviewFiles: document.querySelector("#review-files"),
  reviewVoice: document.querySelector("#review-voice"),
  reviewExecution: document.querySelector("#review-execution"),
  reviewPermission: document.querySelector("#review-permission"),
  backButton: document.querySelector("#back-button"),
  sendButton: document.querySelector("#send-button"),
  receipt: document.querySelector("#receipt"),
  receiptHeading: document.querySelector("#receipt-heading"),
  taskId: document.querySelector("#task-id"),
  copyButton: document.querySelector("#copy-button"),
  againButton: document.querySelector("#again-button"),
  execution: document.querySelector("#execution-hint"),
  permission: document.querySelector("#permission-hint"),
  status: document.querySelector("#status"),
  path: document.querySelector("#path"),
};

const draft = {
  phase: "compose",
  text: "",
  files: [],
  voice: "idle",
  voiceUsed: false,
  taskId: "",
  sending: false,
};

let recognition = null;
let wantListen = false;
let copyTimer = 0;

function announce(message) {
  els.status.textContent = "";
  window.requestAnimationFrame(() => {
    els.status.textContent = message;
  });
}

function fitGoal() {
  els.goal.style.height = "auto";
  const next = Math.min(Math.max(els.goal.scrollHeight, 148), 320);
  els.goal.style.height = `${next}px`;
}

function setPanels() {
  els.compose.hidden = draft.phase !== "compose";
  els.review.hidden = draft.phase !== "review";
  els.receipt.hidden = draft.phase !== "receipt";
  els.stage.dataset.phase = draft.phase;
}

function renderPath() {
  const marks = pathMarks(draft);
  for (const mark of marks) {
    const item = els.path.querySelector(`[data-step="${mark.id}"]`);
    if (!item) continue;
    item.classList.toggle("is-done", mark.done && !mark.current);
    item.classList.toggle("is-next", mark.next);
    if (mark.current) item.setAttribute("aria-current", "step");
    else item.removeAttribute("aria-current");
  }
}

function renderHints() {
  els.execution.textContent = executionHint(draft.phase);
  els.permission.textContent = permissionHint(draft);
}

function renderChips() {
  els.chips.replaceChildren();
  els.chips.hidden = draft.files.length === 0;
  draft.files.forEach((file, index) => {
    const item = document.createElement("li");
    const name = document.createElement("span");
    name.className = "chip-name";
    name.textContent = file.name;
    const size = document.createElement("span");
    size.className = "chip-size";
    size.textContent = formatBytes(file.size);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "chip-remove";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Datei ${file.name} ${COPY.removeLabel}`);
    remove.addEventListener("click", () => {
      draft.files.splice(index, 1);
      renderChips();
      renderPath();
      renderHints();
      els.goal.focus();
    });
    item.append(name, size, remove);
    els.chips.append(item);
  });
}

function syncVoiceControl() {
  const listening = draft.voice === "listening";
  els.voiceLabel.textContent = listening ? COPY.voiceStop : COPY.voice;
  els.voiceButton.setAttribute("aria-pressed", listening ? "true" : "false");
  els.voiceAsk.hidden = draft.voice !== "ask";
  els.voiceCaption.hidden = draft.voice !== "listening";
  els.field.classList.toggle("is-listening", listening);
  if (!listening) els.voiceCaption.textContent = "";
}

function sync() {
  setPanels();
  renderPath();
  renderHints();
  syncVoiceControl();
  const ready = canReview(draft.text);
  els.reviewButton.classList.toggle("is-ready", ready);
  els.reviewButton.setAttribute("aria-disabled", ready ? "false" : "true");
  els.field.classList.toggle("is-lit", document.activeElement === els.goal || draft.text.length > 0);
}

function takeFiles(list) {
  if (draft.phase !== "compose") return;
  const result = addFiles(draft.files, list);
  draft.files = result.files;
  renderChips();
  renderPath();
  renderHints();
  if (result.overflow) announce(COPY.fileLimit);
  else if (result.files.length) announce(`${result.files.length} Datei${result.files.length === 1 ? "" : "en"} ausgewählt. Nur der Name, kein Upload.`);
}

function openReview() {
  const reason = goalBlockReason(draft.text);
  if (reason) {
    announce(reason);
    els.goal.focus();
    return;
  }
  if (draft.voice === "listening") stopVoice();
  draft.phase = "review";
  const review = buildReview(draft);
  els.quote.textContent = review.goal;
  els.reviewFiles.textContent = review.files;
  els.reviewVoice.textContent = review.voice;
  els.reviewExecution.textContent = review.execution;
  els.reviewPermission.textContent = review.permission;
  sync();
  announce("Auftrag prüfen.");
  els.reviewHeading.focus();
}

function backToCompose() {
  draft.phase = "compose";
  draft.sending = false;
  sync();
  fitGoal();
  els.goal.focus();
}

function submitOrder() {
  if (draft.phase !== "review" || draft.sending) return;
  draft.sending = true;
  draft.taskId = createTaskId();
  draft.phase = "receipt";
  els.taskId.textContent = draft.taskId;
  els.copyButton.textContent = COPY.copy;
  sync();
  announce(`Auftrag bereit. Task-ID ${draft.taskId}. ${COPY.executionReceipt}`);
  els.receiptHeading.focus();
}

function resetOrder() {
  stopVoice();
  draft.phase = "compose";
  draft.text = "";
  draft.files = [];
  draft.voice = speechAvailable() ? "idle" : "unsupported";
  draft.voiceUsed = false;
  draft.taskId = "";
  draft.sending = false;
  els.goal.value = "";
  els.fileInput.value = "";
  fitGoal();
  renderChips();
  sync();
  els.goal.focus();
}

async function copyTaskId() {
  const value = draft.taskId;
  if (!value) return;
  try {
    await navigator.clipboard.writeText(value);
  } catch {
    const area = document.createElement("textarea");
    area.value = value;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.left = "-999px";
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
  els.copyButton.textContent = COPY.copied;
  announce(`${COPY.copied}. ${value}`);
  window.clearTimeout(copyTimer);
  copyTimer = window.setTimeout(() => {
    els.copyButton.textContent = COPY.copy;
  }, 1600);
}

function speechAvailable() {
  return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
}

function ensureRecognition() {
  const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Ctor) return null;
  if (recognition) return recognition;
  recognition = new Ctor();
  recognition.lang = "de-DE";
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.onresult = (event) => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const chunk = event.results[i][0].transcript;
      if (event.results[i].isFinal) appendTranscript(chunk);
      else interim += chunk;
    }
    els.voiceCaption.textContent = interim.trim();
  };
  recognition.onerror = (event) => {
    if (event.error === "aborted" || event.error === "no-speech") return;
    wantListen = false;
    if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      draft.voice = "denied";
      sync();
      announce(COPY.permissionDenied);
      return;
    }
    draft.voice = "idle";
    sync();
    announce(COPY.voiceNetwork);
  };
  recognition.onend = () => {
    if (!wantListen) return;
    try {
      recognition.start();
    } catch {
      /* already running */
    }
  };
  return recognition;
}

function appendTranscript(chunk) {
  const addition = String(chunk || "").trim();
  if (!addition) return;
  const current = els.goal.value;
  const spacer = current && !/\s$/.test(current) ? " " : "";
  els.goal.value = `${current}${spacer}${addition}`;
  draft.text = els.goal.value;
  draft.voiceUsed = true;
  fitGoal();
  renderPath();
  sync();
}

function stopVoice() {
  wantListen = false;
  if (draft.voice === "listening" || draft.voice === "ask") draft.voice = "idle";
  if (recognition) {
    try {
      recognition.stop();
    } catch {
      /* already stopped */
    }
  }
  syncVoiceControl();
}

function startVoice() {
  const rec = ensureRecognition();
  if (!rec) {
    draft.voice = "unsupported";
    sync();
    announce(COPY.permissionUnsupported);
    return;
  }
  wantListen = true;
  draft.voice = "listening";
  sync();
  announce(COPY.permissionListening);
  try {
    rec.start();
  } catch {
    /* start can throw if called twice */
  }
  els.voiceButton.focus();
}

function onVoiceClick() {
  if (draft.voice === "listening") {
    stopVoice();
    announce("Sprache beendet.");
    els.goal.focus();
    return;
  }
  if (!speechAvailable() || draft.voice === "unsupported") {
    draft.voice = "unsupported";
    sync();
    announce(COPY.permissionUnsupported);
    return;
  }
  draft.voice = "ask";
  sync();
  announce(COPY.permissionAsk);
  els.voiceAllow.focus();
}

function advance() {
  if (draft.phase === "compose") openReview();
  else if (draft.phase === "review") submitOrder();
}

els.goal.addEventListener("input", () => {
  draft.text = els.goal.value;
  fitGoal();
  sync();
});

els.reviewButton.addEventListener("click", openReview);
els.backButton.addEventListener("click", backToCompose);
els.sendButton.addEventListener("click", submitOrder);
els.againButton.addEventListener("click", resetOrder);
els.copyButton.addEventListener("click", copyTaskId);
els.fileButton.addEventListener("click", () => els.fileInput.click());
els.fileInput.addEventListener("change", () => {
  takeFiles(els.fileInput.files);
  els.fileInput.value = "";
  els.goal.focus();
});
els.voiceButton.addEventListener("click", onVoiceClick);
els.voiceAllow.addEventListener("click", startVoice);
els.voiceDecline.addEventListener("click", () => {
  draft.voice = "idle";
  sync();
  els.voiceButton.focus();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    if (draft.voice === "listening" || draft.voice === "ask") {
      stopVoice();
      if (draft.voice === "ask") draft.voice = "idle";
      sync();
      event.preventDefault();
    } else if (draft.phase === "review") {
      backToCompose();
      event.preventDefault();
    }
    return;
  }
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    event.preventDefault();
    advance();
  }
});

window.addEventListener("dragover", (event) => {
  event.preventDefault();
  if (draft.phase === "compose") els.field.classList.add("is-drop");
});
window.addEventListener("dragleave", (event) => {
  if (event.target === document.documentElement || event.target === document.body) {
    els.field.classList.remove("is-drop");
  }
});
window.addEventListener("drop", (event) => {
  event.preventDefault();
  els.field.classList.remove("is-drop");
  if (event.dataTransfer?.files?.length) takeFiles(event.dataTransfer.files);
});

fitGoal();
renderChips();
sync();
els.goal.focus();
