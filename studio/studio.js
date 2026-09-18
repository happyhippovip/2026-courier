import { updateCompactHQ, localToolActors } from "./compact-hq.js";
import { initOpsBay, selectAgent, getSelectedAgent, renderOpsBay } from "./ops-bay.js";
import {
  resolveLivingRoomAgents,
  resolveLiveHQMetrics,
  resolvePermissionGuardTruth,
  resolveTeacherTruth,
  resolveAcademyEconomics,
  resolveActiveGateTruth,
  resolveLiveOrchestrationTruth,
  resolveReviewTruth,
  resolveLiveAgentMotion,
  resolveChiefAlerts,
  resolveAgentDetailData,
  resolveOpsState,
  normalizeOpsState,
  StorySceneController,
  CANONICAL_EXAMPLE_STORY,
  resolveStoryLivingAgents,
  findWalkingPath,
  HQ_WAYPOINTS,
} from "./execution_truth.js";

const AVATAR_ICONS = {
  "agent-chief-commander": "👑",
  "smart-resource-router": "🧭",
  "agent-human-gate-monitor": "🛡️",
  "agent-thought-curator": "💡",
  "agent-update-steward": "📜",
  "agent-antigravity-bridge": "🚀",
  "agent-courier-relay": "⚡",
  "agent-academy-teacher": "🎓",
  "agent-academy-director": "🏛️",
  "agent-codex-bridge": "💻",
  "agent-snitch": "👁️",
  "agent-asset-validator": "🎨",
  "agent-video-synth": "🎬",
  "agent-channel-dispatcher": "📡",
  "agent-memory-mesh": "🧠",
  "agent-test-guardian": "🧪",
  "agent-loop-supervisor": "🔄",
  "worker-google": "🌐",
  "worker-codex": "💻",
  "worker-cli1": "🖥️",
  "worker-cli2": "⌨️",
};

export class LivingHQController {
  constructor() {
    this.pollInterval = 2000; // Keep live state responsive with half the request/render load.
    this.isPolling = false;
    this.currentView = "overview";
    this.currentMode = "LIVE"; // LIVE ONLY
    this.storyController = new StorySceneController();

    // Viewport Zoom & Pan Camera State
    this.cameraZoom = 1.0;
    this.cameraPanX = 0;
    this.cameraPanY = 0;
    this.isPanning = false;

    // Unclutter & Visual Clarity State
    this.speechMode = "SMART"; // 'SMART' (active/problems/hover only), 'ZEN' (silent/clean), 'ALL' (all speech bubbles)
    this.isTaskBoardCollapsed = (window.innerWidth < 900);
    this.isOpsHudCollapsed = (window.innerWidth < 900);
    this.isCleanMode = false;
    this.hoveredAgentId = null;

    // Simulation State per Agent: id -> { currentX, currentY, targetX, targetY, pathQueue: [], isWalking: false, facing: 1 }
    this.agentSims = new Map();
    this.agentNodes = new Map();
    this.lastAgents = [];
    this.lastLiveAgents = resolveLivingRoomAgents({});
    this.lastMotionFingerprint = null;
    this.lastMotion = null;
    this.lastLiveState = null;

    // Ambient walking patrol timer
    this.lastPatrolTime = Date.now();

    this.initElements();
    this.resetUnverifiedTelemetry();
    this.bindEvents();
    initOpsBay({ openAdvanced: (id) => this.openAgentInspectorFor(id) });
    this.bindOpsBayCards();
    this.startClock();

    // Set initial collapsed state on panels if small screen
    if (this.isTaskBoardCollapsed) this.toggleTaskBoard(true);
    if (this.isOpsHudCollapsed) this.toggleOpsHud(true);

    // Immediately render all default living agents at frame 0
    const initialAgents = resolveLivingRoomAgents({});
    this.lastLiveAgents = initialAgents;
    this.lastAgents = initialAgents;
    this.syncAgentSimulations(initialAgents);
    this.renderLivingAgents(initialAgents);

    this.startAnimationLoop();
    this.startPolling();
  }

  initElements() {
    this.wrapper = document.getElementById("living-hq-wrapper");
    this.stage = document.getElementById("living-hq-stage");
    this.agentsLayer = document.getElementById("living-agents-layer");
    this.courierPacket = document.getElementById("courier-packet");
    this.courierPacketLabel = document.getElementById("courier-packet-label");

    // Chief Alert Bar
    this.chiefAlertBar = document.getElementById("chief-alert-bar");
    this.chiefAlertStream = document.getElementById("chief-alert-stream");

    // Header Controls
    this.serverStatus = document.getElementById("server-status");
    this.liveClock = document.getElementById("hq-live-clock");
    this.contextPillVer = document.getElementById("context-pill-ver");
    this.courierCommitTag = document.getElementById("courier-commit");
    this.camButtons = document.querySelectorAll(".cam-btn");
    this.btn16x9 = document.getElementById("btn-aspect-16-9");
    this.btn9x16 = document.getElementById("btn-aspect-9-16");
    this.btnRecord = document.getElementById("btn-recording-mode");
    this.btnCinematic = document.getElementById("btn-cinematic-mode");
    this.btnToggleDetails = document.getElementById("btn-toggle-details");
    this.btnCloseDrawer = document.getElementById("btn-close-drawer");
    this.drawer = document.getElementById("control-panel-drawer");

    // Unclutter & Toggle Controls
    this.btnToggleTasks = document.getElementById("btn-toggle-tasks");
    this.btnToggleHud = document.getElementById("btn-toggle-hud");
    this.btnToggleSpeech = document.getElementById("btn-toggle-speech");
    this.speechModeLabel = document.getElementById("speech-mode-label");
    this.speechModeIcon = document.getElementById("speech-mode-icon");
    this.btnCleanMode = document.getElementById("btn-clean-mode");

    // Floating Zoom HUD Controls
    this.zoomLevelLabel = document.getElementById("zoom-level-label");
    this.btnZoomIn = document.getElementById("btn-zoom-in");
    this.btnZoomOut = document.getElementById("btn-zoom-out");
    this.btnZoomReset = document.getElementById("btn-zoom-reset");

    // TV Wall Overlays
    this.tvActiveCount = document.getElementById("tv-active-count");
    this.tvCapacityPct = document.getElementById("tv-capacity-pct");
    this.tvLiveWf = document.getElementById("tv-live-wf");
    this.tvLiveCorr = document.getElementById("tv-live-corr");
    this.tvLiveCtx = document.getElementById("tv-live-ctx");
    this.tvLiveSchool = document.getElementById("tv-live-school");
    this.tvLiveTreasury = document.getElementById("tv-live-treasury");

    // Drawer Elements
    this.humanIdeaInput = document.getElementById("human-idea-input");
    this.btnDispatchIdea = document.getElementById("btn-dispatch-idea");
    this.presetButtons = document.querySelectorAll(".preset-btn");
    this.gateBanner = document.getElementById("human-gate-banner");
    this.gateDesc = document.getElementById("gate-desc");
    this.btnGateApprove = document.getElementById("btn-gate-approve");
    this.btnGateReject = document.getElementById("btn-gate-reject");

    // Telemetry Elements
    this.snitchPermStatus = document.getElementById("snitch-perm-status");
    this.snitchPermCommand = document.getElementById("snitch-perm-command");
    this.snitchPermRuleRec = document.getElementById("snitch-perm-rule-rec");
    this.liveWfId = document.getElementById("live-wf-id");
    this.liveWfStatus = document.getElementById("live-wf-status");
    this.liveWfBar = document.getElementById("live-wf-bar");
    this.treasuryEur = document.getElementById("treasury-eur");
    this.treasuryUsd = document.getElementById("treasury-usd");
    this.treasuryVerified = document.getElementById("treasury-verified");
    this.treasuryGoal = document.getElementById("treasury-goal");
    this.panelCtxVer = document.getElementById("panel-ctx-ver");
    this.panelCtxPrev = document.getElementById("panel-ctx-prev");
    this.panelCtxHash = document.getElementById("panel-ctx-hash");
    this.panelRepoCourier = document.getElementById("panel-repo-courier");
    this.panelRepoMemory = document.getElementById("panel-repo-memory");

    // Live Autonomous Organization Operations Panel HUD
    this.opsHudPanel = document.getElementById("live-ops-hud-panel");
    this.opsHudHeaderToggle = document.getElementById("ops-hud-header-toggle");
    this.btnMinOpsHud = document.getElementById("btn-min-ops-hud");
    this.hudOrgStatus = document.getElementById("hud-org-status");
    this.hudCurrentGoal = document.getElementById("hud-current-goal");
    this.hudCurrentTask = document.getElementById("hud-current-task");
    this.hudWorkerProvider = document.getElementById("hud-worker-provider");
    this.hudEnduranceStatus = document.getElementById("hud-endurance-status");
    this.hudGatesStatus = document.getElementById("hud-gates-status");
    this.hudSnitchStatus = document.getElementById("hud-snitch-status");
    this.hudLastResult = document.getElementById("hud-last-result");

    // Needs You Attention Banner
    this.hudNeedsYou = document.getElementById("hud-needs-you");
    this.hudNeedsYouIcon = document.getElementById("hud-needs-you-icon");
    this.hudNeedsYouText = document.getElementById("hud-needs-you-text");

    // Result Feed
    this.hudResultFeedList = document.getElementById("hud-result-feed-list");

    // Live Task Board Panel
    this.taskBoardPanel = document.getElementById("live-task-board-panel");
    this.taskBoardHeaderToggle = document.getElementById("task-board-header-toggle");
    this.btnMinTaskBoard = document.getElementById("btn-min-task-board");
    this.taskBoardCount = document.getElementById("task-board-count");
    this.taskBoardFilters = document.querySelectorAll(".tb-filter");
    this.taskBoardCards = document.getElementById("task-board-cards");
    this.currentTaskFilter = "ALL";
    this.lastTaskBoardData = [];

    // Operations Cockpit Modals
    this.btnRefreshState = document.getElementById("btn-refresh-state");
    this.btnToggleTimeline = document.getElementById("btn-toggle-timeline");
    this.btnToggleMorning = document.getElementById("btn-toggle-morning");
    this.inspectorModalBackdrop = document.getElementById("inspector-modal-backdrop");
    this.inspectorModalTitle = document.getElementById("inspector-modal-title");
    this.inspectorModalBody = document.getElementById("inspector-modal-body");
    this.btnCloseInspector = document.getElementById("btn-close-inspector");
    this.reportModalBackdrop = document.getElementById("report-modal-backdrop");
    this.reportModalTitle = document.getElementById("report-modal-title");
    this.reportModalBody = document.getElementById("report-modal-body");
    this.btnCloseReport = document.getElementById("btn-close-report");
  }

  /** Replace static markup placeholders before the first local state refresh. */
  resetUnverifiedTelemetry() {
    if (this.courierCommitTag) this.courierCommitTag.textContent = "HEAD: UNAVAILABLE";
    if (this.contextPillVer) this.contextPillVer.textContent = "CONTEXT: UNKNOWN";
    if (this.tvLiveCorr) this.tvLiveCorr.textContent = "NONE";
    if (this.tvLiveCtx) this.tvLiveCtx.textContent = "UNKNOWN";
    if (this.tvLiveSchool) this.tvLiveSchool.textContent = "UNKNOWN";
    if (this.liveWfId) this.liveWfId.textContent = "NONE";
    if (this.treasuryEur) this.treasuryEur.textContent = "UNKNOWN";
    if (this.treasuryUsd) this.treasuryUsd.textContent = "UNAVAILABLE";
    if (this.treasuryVerified) this.treasuryVerified.textContent = "NOT_VERIFIED";
    if (this.treasuryGoal) this.treasuryGoal.textContent = "NOT_VERIFIED";
    if (this.panelCtxVer) this.panelCtxVer.textContent = "UNKNOWN";
    if (this.panelCtxPrev) this.panelCtxPrev.textContent = "UNKNOWN";
    if (this.panelCtxHash) this.panelCtxHash.textContent = "UNAVAILABLE";
    if (this.panelRepoCourier) this.panelRepoCourier.textContent = "UNAVAILABLE";
    if (this.panelRepoMemory) this.panelRepoMemory.textContent = "UNAVAILABLE";
  }

  bindEvents() {
    // Camera Preset Buttons
    this.camButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        const view = btn.getAttribute("data-view");
        this.setCameraView(view);
      });
    });

    // Mouse Wheel / Trackpad Viewport Zoom (Pointer-Centered)
    this.wrapper?.addEventListener("wheel", (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.12 : 0.89;
      this.setZoom(this.cameraZoom * zoomFactor, e.clientX, e.clientY, false);
    }, { passive: false });

    // Click-and-Drag Pan Interaction
    let startX = 0;
    let startY = 0;
    let initialPanX = 0;
    let initialPanY = 0;

    const onMouseDown = (e) => {
      // Do not initiate pan on buttons, drawer inputs, or interactive controls
      if (e.target.closest("button, input, select, .agent-nameplate, .agent-avatar-body, .hq-zoom-controls, #control-panel-drawer")) {
        return;
      }
      this.isPanning = true;
      startX = e.clientX;
      startY = e.clientY;
      initialPanX = this.cameraPanX;
      initialPanY = this.cameraPanY;
      this.applyCameraTransform(false);
    };

    const onMouseMove = (e) => {
      if (!this.isPanning) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      this.cameraPanX = initialPanX + dx;
      this.cameraPanY = initialPanY + dy;
      this.clampPanBounds();
      this.applyCameraTransform(false);
    };

    const onMouseUp = () => {
      if (this.isPanning) {
        this.isPanning = false;
        this.applyCameraTransform(false);
      }
    };

    this.wrapper?.addEventListener("mousedown", onMouseDown);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);

    // Zoom Buttons
    this.btnZoomIn?.addEventListener("click", () => {
      const rect = this.wrapper?.getBoundingClientRect();
      const cx = rect ? rect.left + rect.width / 2 : null;
      const cy = rect ? rect.top + rect.height / 2 : null;
      this.setZoom(this.cameraZoom + 0.25, cx, cy, true);
    });

    this.btnZoomOut?.addEventListener("click", () => {
      const rect = this.wrapper?.getBoundingClientRect();
      const cx = rect ? rect.left + rect.width / 2 : null;
      const cy = rect ? rect.top + rect.height / 2 : null;
      this.setZoom(this.cameraZoom - 0.25, cx, cy, true);
    });

    this.btnZoomReset?.addEventListener("click", () => this.resetCamera(true));
    this.zoomLevelLabel?.addEventListener("click", () => this.resetCamera(true));

    // Aspect & Mode Toggles
    this.btn16x9?.addEventListener("click", () => {
      this.btn16x9.classList.add("active");
      this.btn9x16.classList.remove("active");
      document.body.classList.remove("mode-9-16");
    });

    this.btn9x16?.addEventListener("click", () => {
      this.btn9x16.classList.add("active");
      this.btn16x9.classList.remove("active");
      document.body.classList.add("mode-9-16");
    });

    this.btnRecord?.addEventListener("click", () => {
      document.body.classList.toggle("mode-recording");
      this.btnRecord.classList.toggle("active");
    });

    this.btnCinematic?.addEventListener("click", () => {
      document.body.classList.toggle("mode-cinematic");
      this.btnCinematic.classList.toggle("active");
    });

    this.btnToggleDetails?.addEventListener("click", () => {
      this.drawer?.classList.toggle("hidden");
    });

    this.btnCloseDrawer?.addEventListener("click", () => {
      this.drawer?.classList.add("hidden");
    });

    this.presetButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        const idea = btn.getAttribute("data-idea");
        if (this.humanIdeaInput && idea) {
          this.humanIdeaInput.value = idea;
        }
      });
    });

    this.btnDispatchIdea?.addEventListener("click", () => this.dispatchHumanIdea());
    this.btnGateApprove?.addEventListener("click", () => this.sendGateDecision(true));
    this.btnGateReject?.addEventListener("click", () => this.sendGateDecision(false));

    // Live Task Board Filter Buttons
    this.taskBoardFilters?.forEach(btn => {
      btn.addEventListener("click", () => {
        this.taskBoardFilters.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        this.currentTaskFilter = btn.getAttribute("data-filter") || "ALL";
        this.renderTaskBoard(this.lastTaskBoardData);
      });
    });

    // Task Board Minimize & Header Toggles
    this.btnMinTaskBoard?.addEventListener("click", (e) => {
      e.stopPropagation();
      this.toggleTaskBoard();
    });
    this.taskBoardHeaderToggle?.addEventListener("click", () => this.toggleTaskBoard());
    this.btnToggleTasks?.addEventListener("click", () => this.toggleTaskBoard());

    // Operations HUD Minimize & Header Toggles
    this.btnMinOpsHud?.addEventListener("click", (e) => {
      e.stopPropagation();
      this.toggleOpsHud();
    });
    this.opsHudHeaderToggle?.addEventListener("click", () => this.toggleOpsHud());
    this.btnToggleHud?.addEventListener("click", () => this.toggleOpsHud());

    // Speech Mode & Zen View Toggles
    this.btnToggleSpeech?.addEventListener("click", () => this.cycleSpeechMode());
    this.btnCleanMode?.addEventListener("click", () => this.toggleCleanMode());

    // Keyboard Shortcuts (T: Tasks, H: HUD, S: Speech, Z: Zen/Clean, Esc: Close)
    window.addEventListener("keydown", (e) => {
      if (e.target.closest("input, textarea, select")) return;
      const key = e.key.toUpperCase();
      if (key === "T") this.toggleTaskBoard();
      if (key === "H") this.toggleOpsHud();
      if (key === "S") this.cycleSpeechMode();
      if (key === "Z") this.toggleCleanMode();
      if (key === "ESCAPE") {
        this.closeInspectorModal();
        this.closeReportModal();
        if (this.drawer && !this.drawer.classList.contains("hidden")) {
          this.drawer.classList.add("hidden");
        }
      }
    });

    // Operations Cockpit Modals & Safe Controls
    this.btnRefreshState?.addEventListener("click", () => this.pollImmediately());
    this.btnToggleTimeline?.addEventListener("click", () => this.openTimelineModal());
    this.btnToggleMorning?.addEventListener("click", () => this.openMorningReportModal());
    this.btnCloseInspector?.addEventListener("click", () => this.closeInspectorModal());
    this.btnCloseReport?.addEventListener("click", () => this.closeReportModal());

    this.inspectorModalBackdrop?.addEventListener("click", (e) => {
      if (e.target === this.inspectorModalBackdrop) this.closeInspectorModal();
    });
    this.reportModalBackdrop?.addEventListener("click", (e) => {
      if (e.target === this.reportModalBackdrop) this.closeReportModal();
    });
  }

  toggleTaskBoard(forceState = null) {
    this.isTaskBoardCollapsed = forceState !== null ? forceState : !this.isTaskBoardCollapsed;
    if (this.taskBoardPanel) {
      this.taskBoardPanel.classList.toggle("collapsed", this.isTaskBoardCollapsed);
    }
    if (this.btnMinTaskBoard) {
      this.btnMinTaskBoard.textContent = this.isTaskBoardCollapsed ? "+" : "−";
      this.btnMinTaskBoard.title = this.isTaskBoardCollapsed ? "Expand Task Board" : "Minimize Task Board";
    }
    if (this.btnToggleTasks) {
      this.btnToggleTasks.classList.toggle("active", !this.isTaskBoardCollapsed);
    }
  }

  toggleOpsHud(forceState = null) {
    this.isOpsHudCollapsed = forceState !== null ? forceState : !this.isOpsHudCollapsed;
    if (this.opsHudPanel) {
      this.opsHudPanel.classList.toggle("collapsed", this.isOpsHudCollapsed);
    }
    if (this.btnMinOpsHud) {
      this.btnMinOpsHud.textContent = this.isOpsHudCollapsed ? "+" : "−";
      this.btnMinOpsHud.title = this.isOpsHudCollapsed ? "Expand Operations HUD" : "Minimize Operations HUD";
    }
    if (this.btnToggleHud) {
      this.btnToggleHud.classList.toggle("active", !this.isOpsHudCollapsed);
    }
  }

  cycleSpeechMode() {
    if (this.speechMode === "SMART") {
      this.speechMode = "ZEN";
    } else if (this.speechMode === "ZEN") {
      this.speechMode = "ALL";
    } else {
      this.speechMode = "SMART";
    }
    if (this.speechModeLabel) this.speechModeLabel.textContent = this.speechMode;
    if (this.speechModeIcon) {
      this.speechModeIcon.textContent = this.speechMode === "ZEN" ? "🔇" : (this.speechMode === "ALL" ? "📢" : "💬");
    }
    if (this.btnToggleSpeech) {
      this.btnToggleSpeech.classList.toggle("active", this.speechMode !== "ZEN");
      this.btnToggleSpeech.title = `Speech Mode: ${this.speechMode} (Click to toggle SMART / ZEN / ALL)`;
    }
    if (this.lastAgents) {
      this.renderLivingAgents(this.lastAgents, this.lastMotion);
    }
  }

  toggleCleanMode() {
    this.isCleanMode = !this.isCleanMode;
    document.body.classList.toggle("mode-zen", this.isCleanMode);
    if (this.btnCleanMode) {
      this.btnCleanMode.classList.toggle("active", this.isCleanMode);
    }
    if (this.isCleanMode) {
      this.toggleTaskBoard(true);
      this.toggleOpsHud(true);
    }
  }

  applyCameraTransform(smooth = false) {
    if (!this.stage) return;
    if (smooth) {
      this.stage.style.transition = "transform 0.4s cubic-bezier(0.16, 1, 0.3, 1)";
    } else {
      this.stage.style.transition = "none";
    }

    this.stage.style.transform = `translate(${this.cameraPanX.toFixed(1)}px, ${this.cameraPanY.toFixed(1)}px) scale(${this.cameraZoom.toFixed(2)})`;
    if (this.zoomLevelLabel) {
      this.zoomLevelLabel.textContent = `${Math.round(this.cameraZoom * 100)}%`;
    }
    if (this.wrapper) {
      this.wrapper.style.cursor = this.isPanning ? "grabbing" : (this.cameraZoom > 1.05 ? "grab" : "default");
    }
  }

  setZoom(newZoom, centerX = null, centerY = null, smooth = false) {
    const oldZoom = this.cameraZoom;
    const clampedZoom = Math.max(0.5, Math.min(2.5, newZoom));
    if (Math.abs(clampedZoom - oldZoom) < 0.001) return;

    if (centerX !== null && centerY !== null && this.wrapper) {
      const rect = this.wrapper.getBoundingClientRect();
      const cursorX = centerX - rect.left - rect.width / 2;
      const cursorY = centerY - rect.top - rect.height / 2;

      const zoomRatio = clampedZoom / oldZoom;
      this.cameraPanX = cursorX - (cursorX - this.cameraPanX) * zoomRatio;
      this.cameraPanY = cursorY - (cursorY - this.cameraPanY) * zoomRatio;
    }

    this.cameraZoom = clampedZoom;
    this.clampPanBounds();
    this.applyCameraTransform(smooth);
  }

  clampPanBounds() {
    if (!this.wrapper || !this.stage) return;
    const rect = this.wrapper.getBoundingClientRect();
    const maxPanX = Math.max(0, (rect.width * this.cameraZoom - rect.width) / 2 + 150);
    const maxPanY = Math.max(0, (rect.height * this.cameraZoom - rect.height) / 2 + 120);

    this.cameraPanX = Math.max(-maxPanX, Math.min(maxPanX, this.cameraPanX));
    this.cameraPanY = Math.max(-maxPanY, Math.min(maxPanY, this.cameraPanY));
  }

  resetCamera(smooth = true) {
    this.cameraZoom = 1.0;
    this.cameraPanX = 0;
    this.cameraPanY = 0;
    this.currentView = "overview";
    this.applyCameraTransform(smooth);
    this.camButtons?.forEach(b => {
      b.classList.toggle("active", b.getAttribute("data-view") === "overview");
    });
  }

  setTruthMode(mode) {
    this.currentMode = "LIVE"; // LIVE ONLY
  }

  setCameraView(view) {
    this.currentView = view;
    if (!this.stage || !this.wrapper) return;

    this.camButtons?.forEach(b => {
      b.classList.toggle("active", b.getAttribute("data-view") === view);
    });

    if (view === "overview") {
      this.resetCamera(true);
      return;
    }

    const rect = this.wrapper.getBoundingClientRect();
    const W = rect.width;
    const H = rect.height;

    let targetX = 50.0;
    let targetY = 50.0;
    let targetZoom = 1.8;

    if (view === "command") {
      targetX = 50.0;
      targetY = 42.0;
      targetZoom = 1.8;
    } else if (view === "tvwall") {
      targetX = 52.0;
      targetY = 18.0;
      targetZoom = 1.9;
    } else if (view === "bodyguards") {
      targetX = 35.0;
      targetY = 72.0;
      targetZoom = 1.7;
    } else if (view === "academy") {
      targetX = 80.0;
      targetY = 48.0;
      targetZoom = 1.8;
    } else if (view === "server") {
      targetX = 85.0;
      targetY = 25.0;
      targetZoom = 1.9;
    } else if (view === "sauna") {
      targetX = 78.0;
      targetY = 16.0;
      targetZoom = 1.9;
    } else if (view === "active") {
      const active = this.lastAgents?.find(a => a.is_active && !a.is_bodyguard) || this.lastAgents?.find(a => a.is_active);
      if (active) {
        targetX = active.x;
        targetY = active.y;
        targetZoom = 2.0;
      }
    }

    this.cameraZoom = targetZoom;
    this.cameraPanX = (50.0 - targetX) * (W / 100) * targetZoom;
    this.cameraPanY = (50.0 - targetY) * (H / 100) * targetZoom;
    this.clampPanBounds();
    this.applyCameraTransform(true);
  }

  startClock() {
    const update = () => {
      if (document.hidden) return;
      const now = new Date();
      const str = now.toUTCString().split(" ")[4];
      if (this.liveClock) this.liveClock.textContent = `HQ TIME: ${str} UTC`;
    };
    update();
    setInterval(update, 1000);
  }

  // ------------------------------------------------------------------------
  // Cap movement work at 30 FPS; idle and hidden rooms do no frame work.
  // CSS water animation remains independent of agent telemetry.
  // ------------------------------------------------------------------------
  startAnimationLoop() {
    let lastTime = performance.now();
    let frame = null;
    const loop = (time) => {
      frame = null;
      if (document.hidden) return;
      const elapsed = time - lastTime;
      if (elapsed >= 1000 / 30) {
        lastTime = time;
        const moving = [...this.agentSims.values()].some(sim => sim.pathQueue?.length || sim.isWalking);
        if (moving) {
          this.updateAgentPositions(Math.min(elapsed / 1000, 0.1));
          if (this.currentMode === "LIVE" && this.lastAgents && this.lastLiveState) {
            this.updateCourierTransport(this.lastAgents, this.lastLiveState, this.lastMotion);
          }
        }
      }
      if ([...this.agentSims.values()].some(sim => sim.pathQueue?.length || sim.isWalking)) {
        frame = requestAnimationFrame(loop);
      }
    };
    this.wakeAnimation = () => {
      if (!document.hidden && frame === null) {
        lastTime = performance.now();
        frame = requestAnimationFrame(loop);
      }
    };
    document.addEventListener("visibilitychange", () => {
      document.body.classList.toggle("hq-paused", document.hidden);
      if (document.hidden && frame !== null) {
        cancelAnimationFrame(frame);
        frame = null;
      } else this.wakeAnimation();
    });
    this.wakeAnimation();
  }

  updateAgentPositions(delta) {
    const WALK_SPEED = 18.0; // % per second

    for (const [id, sim] of this.agentSims.entries()) {
      const node = this.agentNodes.get(id);
      if (!node) continue;
      if (!sim.pathQueue?.length && !sim.isWalking && node.style.left) continue;

      if (sim.pathQueue && sim.pathQueue.length > 0) {
        const nextWp = sim.pathQueue[0];
        const dx = nextWp.x - sim.currentX;
        const dy = nextWp.y - sim.currentY;
        const dist = Math.hypot(dx, dy);

        if (dist <= 0.6) {
          // Reached waypoint
          sim.currentX = nextWp.x;
          sim.currentY = nextWp.y;
          sim.pathQueue.shift();
        } else {
          // Step towards waypoint
          const moveDist = WALK_SPEED * delta;
          const ratio = Math.min(moveDist / dist, 1.0);
          sim.currentX += dx * ratio;
          sim.currentY += dy * ratio;

          // Update facing direction
          if (Math.abs(dx) > 0.1) {
            sim.facing = dx > 0 ? 1 : -1;
          }
        }

        sim.isWalking = true;
      } else {
        sim.isWalking = false;
      }

      // Apply coordinates and classes to DOM node
      node.style.left = `${sim.currentX.toFixed(2)}%`;
      node.style.top = `${sim.currentY.toFixed(2)}%`;

      node.classList.toggle("is-walking", sim.isWalking);
      node.classList.toggle("facing-left", sim.facing === -1);
      node.classList.toggle("facing-right", sim.facing === 1);
    }
  }

  // ------------------------------------------------------------------------
  // Polling Machine State & Dispatching Waypoint Paths
  // ------------------------------------------------------------------------
  async startPolling() {
    if (this.isPolling) return;
    this.isPolling = true;

    const poll = async () => {
      if (document.hidden) {
        setTimeout(poll, this.pollInterval);
        return;
      }
      try {
        const response = await fetch("/api/state", { cache: "no-store" });
        if (!response.ok) throw new Error(`State API: ${response.status}`);
        if (response.ok) {
          const stateData = await response.json();
          try {
            const localResponse = await fetch('/api/local-tools', {cache:'no-store', signal:AbortSignal.timeout(3000)});
            stateData.local_tools = localResponse.ok ? await localResponse.json() : null;
          } catch { stateData.local_tools = null; }
          this.updateLivingHQ(stateData);
          this.wakeAnimation?.();
          if (this.serverStatus) this.serverStatus.textContent = "LIVE BUS CONNECTED";
        }
      } catch (err) {
        updateCompactHQ({});
        if (this.serverStatus) this.serverStatus.textContent = "RECONNECTING LOCAL BUS...";
      } finally {
        setTimeout(poll, this.pollInterval);
      }
    };

    poll();
  }

  enqueueRoute(agentId, waypointKeys) {
    let sim = this.agentSims.get(agentId);
    if (!sim || !waypointKeys || waypointKeys.length === 0) return;

    let fullPath = [];
    let curX = sim.currentX;
    let curY = sim.currentY;

    for (const wpKey of waypointKeys) {
      const wp = HQ_WAYPOINTS[wpKey];
      if (!wp) continue;
      const seg = findWalkingPath(curX, curY, wp.x, wp.y);
      fullPath.push(...seg);
      curX = wp.x;
      curY = wp.y;
    }

    if (fullPath.length > 0) {
      sim.targetX = fullPath[fullPath.length - 1].x;
      sim.targetY = fullPath[fullPath.length - 1].y;
      sim.pathQueue = fullPath;
    }
  }

  setAgentTarget(agentId, targetX, targetY) {
    let sim = this.agentSims.get(agentId);
    if (!sim) return;
    const dist = Math.hypot(targetX - sim.targetX, targetY - sim.targetY);
    if (dist > 1.5) {
      sim.targetX = targetX;
      sim.targetY = targetY;
      sim.pathQueue = findWalkingPath(sim.currentX, sim.currentY, targetX, targetY);
    }
  }

  bindOpsBayCards() {
    if (this.opsCardsBound) return;
    const museCard = document.getElementById("muse-main");
    if (museCard) {
      museCard.style.cursor = "pointer";
      museCard.addEventListener("click", () => selectAgent("muse", { name: "MUSE", title: "MAIN WORKER", icon: "∞" }));
      this.opsCardsBound = true;
    }
    for (let n = 1; n <= 8; n++) {
      const slot = document.getElementById(`cli-slot-${n}`);
      if (slot && !slot.dataset.opsBound) {
        slot.dataset.opsBound = "1";
        slot.style.cursor = "pointer";
        const label = `CLI${n}`;
        slot.addEventListener("click", () => selectAgent(`cli${n}`, { name: label, title: "OPERATOR", icon: "▫" }));
      }
    }
    for (const [id, key] of [["rail-chatgpt", "codex"], ["rail-antigravity", "google"]]) {
      const card = document.getElementById(id);
      if (card && !card.dataset.opsBound) {
        card.dataset.opsBound = "1";
        card.style.cursor = "pointer";
        card.addEventListener("click", () => {
          const a = (this.lastAgents || []).find(x => x.provider === key || (x.id || "").includes(key)) || {};
          selectAgent(key, { name: a.name || key.toUpperCase(), title: a.title || a.role, icon: a.icon });
        });
      }
    }
  }

  openAgentInspectorFor(id) {
    const live = (this.lastAgents || []).find(a => a.id === id)
      || (this.lastAgents || []).find(a => (a.provider || "").toLowerCase().includes(id))
      || { id, name: id.toUpperCase() };
    this.openAgentInspector(live);
  }

  updateTruthPanel(stateData) {
    const set = (id, v) => { const n = document.getElementById(id); if (n) n.textContent = v; };
    const L = stateData?.courier_ledger || {};
    set("tv-truth-ledger", L.status && L.status !== "UNKNOWN" ? `${L.status} · r${L.revision ?? "?"}` : "UNKNOWN");
    set("tv-truth-guard", L.guard || "UNKNOWN");
    set("tv-truth-unproven", L.unproven_count ?? "UNKNOWN");
    set("tv-truth-clean", L.clean_idle || "UNKNOWN");
    set("tv-truth-qi", L.queue_independent || "UNKNOWN");
    const next = L.next_action && L.next_action !== "UNKNOWN" ? L.next_action.replace(/^Prove edge:\s*/, "") : "UNKNOWN";
    set("tv-truth-next", next);
    const head = stateData?.repo_head_sha;
    set("tv-truth-head", typeof head === "string" && head !== "UNKNOWN" ? head.slice(0, 12) : "UNKNOWN");
    const co = document.getElementById("co-truth");
    if (co) {
      const v = (x) => (x === null || x === undefined || x === "UNKNOWN" ? "—" : String(x));
      const hs = typeof head === "string" && head !== "UNKNOWN" ? head.slice(0, 12) : "—";
      co.textContent = `LEDGER ${v(L.status)} · GUARD ${v(L.guard)} · QUEUE ${v(L.queue_independent)} · CLEAN ${v(L.clean_idle)} · UNPROVEN ${L.unproven_count ?? "—"} · HEAD ${hs}`;
    }
  }

  updateLivingHQ(stateData) {
    this.lastLiveState = stateData;
    // Single ops_state: every display surface derives agent state from here.
    this.lastOpsState = resolveOpsState(stateData);
    updateCompactHQ(stateData, this.lastOpsState);
    this.bindOpsBayCards();
    this.updateTruthPanel(stateData);
    renderOpsBay(this.lastOpsState, stateData);
    // 1. Resolve Dynamic Living Agents from real telemetry
    const localActors = localToolActors(stateData.local_tools);
    const agents = resolveLivingRoomAgents(stateData).filter(a => !['agent-codex-bridge','agent-antigravity-bridge'].includes(a.id));
    agents.push(...localActors);
    this.lastLiveAgents = agents;

    // 2. Resolve Deterministic Live Agent Motion
    const motion = resolveLiveAgentMotion(stateData, this.lastMotion);
    this.lastMotion = motion;

    // In LIVE mode, update simulations and courier directly
    if (this.currentMode === "LIVE") {
      this.lastAgents = agents;
      this.syncAgentSimulations(agents);

      // Check for motion state changes (suppress duplicates)
      if (motion.fingerprint !== this.lastMotionFingerprint) {
        this.lastMotionFingerprint = motion.fingerprint;

        if (motion.is_idle) {
          // Return all agents to their home workstations
          for (const agent of agents) {
            this.setAgentTarget(agent.id, agent.homeX || agent.x, agent.homeY || agent.y);
          }
        } else {
          for (const [agentId, routeWps] of Object.entries(motion.routes)) {
            this.enqueueRoute(agentId, routeWps);
          }
          for (const [agentId, dest] of Object.entries(motion.destinations)) {
            if (!motion.routes[agentId]) {
              this.setAgentTarget(agentId, dest.x, dest.y);
            }
          }
        }
      }

      // Position app actors independently of the Courier orchestration fingerprint.
      for (const actor of localActors) this.setAgentTarget(actor.id, actor.targetX, actor.targetY);
      this.renderLivingAgents(agents, motion);
      this.updateCourierTransport(agents, stateData, motion);
    }

    // 2.5 Update Persistent Chief Alert Bar
    this.updateChiefAlertBar(stateData);

    // 3. Resolve Master TV Wall Data
    const metrics = resolveLiveHQMetrics(stateData);
    if (this.tvActiveCount) this.tvActiveCount.textContent = metrics.active_agents;
    if (this.tvCapacityPct) this.tvCapacityPct.textContent = `${Math.round((metrics.active_agents / 40) * 100 * 10) / 10}% Capacity`;

    const wf = metrics.current_workflow || "NONE";
    const corr = metrics.correlation_id || "NONE";
    const ctxVer = metrics.context_version ? `v${metrics.context_version}` : "UNKNOWN";

    if (this.tvLiveWf) this.tvLiveWf.textContent = wf;
    if (this.tvLiveCorr) this.tvLiveCorr.textContent = corr;
    if (this.tvLiveCtx) this.tvLiveCtx.textContent = ctxVer;
    if (this.contextPillVer) this.contextPillVer.textContent = `CONTEXT: ${ctxVer}`;

    const teacher = resolveTeacherTruth(stateData);
    const nextSchool = teacher.next_school_time || "UNKNOWN";
    if (this.tvLiveSchool) this.tvLiveSchool.textContent = nextSchool;

    // Invariant: Flow indicator
    const isFlowActive = Boolean(wf && wf !== "IDLE_MONITORING");
    this.stage?.classList.toggle("is-flow-active", isFlowActive);

    // 3.5 Update Live Autonomous Organization Operations Panel HUD
    const autoRuntime = stateData?.autonomy_runtime || {};
    const endurance = stateData?.endurance_188g || {};
    const anomalies = stateData?.anomalies || {};

    const orgStatus = autoRuntime.status || "IDLE_EXPECTED";
    if (this.hudOrgStatus) {
      this.hudOrgStatus.textContent = orgStatus;
      this.hudOrgStatus.className = `ops-hud-badge ${orgStatus.includes("RUNNING") ? "running" : (orgStatus.includes("GATE") ? "gate" : "")}`;
    }

    if (this.hudCurrentGoal) {
      this.hudCurrentGoal.textContent = autoRuntime.current_goal || "Autonomous Standby";
    }

    if (this.hudCurrentTask) {
      this.hudCurrentTask.textContent = autoRuntime.current_action || "None (Safe Standby)";
    }

    // Determine active worker and provider
    const activeAgentsList = agents.filter(a => a.is_active || a.state === "RUNNING" || a.state === "WORKING");
    if (this.hudWorkerProvider) {
      if (activeAgentsList.length > 0) {
        const top = activeAgentsList[0];
        this.hudWorkerProvider.textContent = `${top.name} • ${top.task || 'ACTIVE'}`;
      } else {
        this.hudWorkerProvider.textContent = `STANDBY (0 / ${agents.length} active slots)`;
      }
    }

    // 188G Endurance Status (Strict Read-Only)
    if (this.hudEnduranceStatus) {
      const elapsedSec = endurance.elapsed_seconds || 0;
      const targetHours = endurance.duration_target_hours || 8.0;
      const elapsedHours = (elapsedSec / 3600).toFixed(2);
      const pct = Math.min(100, Math.round((elapsedSec / (targetHours * 3600)) * 1000) / 10);
      const isAlive = endurance.is_running || endurance.status === "IDLE_EXPECTED";
      const idleModelCalls = endurance.model_calls_during_idle || 0;
      this.hudEnduranceStatus.textContent = `${isAlive ? 'RUNNING' : 'STANDBY'} (${elapsedHours}h / ${targetHours}h • ${pct}%) • ${idleModelCalls} idle calls`;
    }

    // Gates Status
    if (this.hudGatesStatus) {
      const humanGatesCount = (autoRuntime.human_gates || []).length;
      const moneyGatesCount = (autoRuntime.money_gates || []).length;
      if (humanGatesCount > 0 || moneyGatesCount > 0) {
        this.hudGatesStatus.textContent = `PARKED: ${humanGatesCount} Human Gate(s) • ${moneyGatesCount} Money Gate(s)`;
        this.hudGatesStatus.className = "ops-hud-val text-orange";
      } else {
        this.hudGatesStatus.textContent = `0 EUR (PASS) • PUB: SAFE (DENY)`;
        this.hudGatesStatus.className = "ops-hud-val text-green";
      }
    }

    // Snitch Anomaly Status
    if (this.hudSnitchStatus) {
      const qBranches = anomalies.quarantined_branches || [];
      const qScopes = anomalies.quarantined_scopes || [];
      if (qBranches.length > 0 || qScopes.length > 0) {
        this.hudSnitchStatus.textContent = `QUARANTINED: ${qBranches.join(', ') || qScopes.join(', ')}`;
        this.hudSnitchStatus.className = "ops-hud-val text-orange";
      } else {
        this.hudSnitchStatus.textContent = `HEALTHY (0 Quarantined Branches)`;
        this.hudSnitchStatus.className = "ops-hud-val text-green";
      }
    }

    // Last Result
    if (this.hudLastResult) {
      const compJobs = autoRuntime.jobs_completed || [];
      if (compJobs.length > 0) {
        const lastJob = compJobs[compJobs.length - 1];
        this.hudLastResult.textContent = typeof lastJob === "string" ? lastJob : (lastJob.task_id || JSON.stringify(lastJob));
      } else {
        this.hudLastResult.textContent = "None (No recent completed tasks)";
      }
    }

    // 3.6 Update User Attention Panel: NEEDS YOU
    const gateTruth = resolveActiveGateTruth(stateData?.bus);
    this.updateNeedsYouBanner(autoRuntime, stateData?.bus, gateTruth);

    // 3.7 Update Live Result Feed
    const resultEvents = stateData?.result_feed || [];
    this.updateResultFeed(resultEvents);

    // 3.8 Update Live Task Board
    const taskBoardItems = stateData?.task_board || [];
    this.renderTaskBoard(taskBoardItems);

    // 4. Update Telemetry Panels & Human Gate
    this.updateTelemetryAndGate(stateData, metrics);
  }

  updateNeedsYouBanner(autoRuntime, busState, gateTruth) {
    if (!this.hudNeedsYou) return;
    const humanGates = autoRuntime.human_gates || [];
    const moneyGates = autoRuntime.money_gates || [];

    if (gateTruth.is_active || humanGates.length > 0) {
      const topTask = humanGates[0]?.task_id || "Human Approval";
      this.hudNeedsYou.className = "ops-needs-you-banner attention";
      if (this.hudNeedsYouIcon) this.hudNeedsYouIcon.textContent = "🚨";
      if (this.hudNeedsYouText) this.hudNeedsYouText.textContent = `NEEDS YOU: Human Approval Required (${topTask})`;
    } else if (moneyGates.length > 0) {
      const topTask = moneyGates[0]?.task_id || "Payment Review";
      this.hudNeedsYou.className = "ops-needs-you-banner attention";
      if (this.hudNeedsYouIcon) this.hudNeedsYouIcon.textContent = "💳";
      if (this.hudNeedsYouText) this.hudNeedsYouText.textContent = `NEEDS YOU: Payment Approval (0 EUR Limit) (${topTask})`;
    } else {
      this.hudNeedsYou.className = "ops-needs-you-banner safe";
      if (this.hudNeedsYouIcon) this.hudNeedsYouIcon.textContent = "🟢";
      if (this.hudNeedsYouText) this.hudNeedsYouText.textContent = "NEEDS YOU: NOTHING (You can safely walk away)";
    }
  }

  updateResultFeed(resultFeed) {
    if (!this.hudResultFeedList) return;
    if (!resultFeed || resultFeed.length === 0) {
      this.hudResultFeedList.innerHTML = '<div class="result-feed-item text-muted">No recent events recorded</div>';
      return;
    }
    const recent = resultFeed.slice(-6).reverse();
    this.hudResultFeedList.innerHTML = recent.map(ev => {
      const timeStr = ev.ingested_at ? ev.ingested_at.split('T')[1]?.substring(0, 8) : '';
      const type = ev.event_type || 'EVENT';
      const outcome = ev.outcome || 'OK';
      const worker = ev.source_worker ? `@${ev.source_worker}` : '';
      const cls = outcome === 'SUCCESS' ? 'SUCCESS' : (type === 'HUMAN_GATE' ? 'GATE' : (outcome === 'FAIL' ? 'ANOMALY' : ''));
      return `<div class="result-feed-item ${cls}">[${timeStr}] <b>${type}</b>: ${ev.task_id || ''} ${worker} (${outcome})</div>`;
    }).join('');
  }

  renderTaskBoard(tasks) {
    if (!this.taskBoardCards) return;
    this.lastTaskBoardData = tasks || [];

    const filtered = this.lastTaskBoardData.filter(t => {
      if (this.currentTaskFilter === "ALL") return true;
      if (this.currentTaskFilter === "READY") return t.status === "READY" || t.status === "BACKLOG";
      if (this.currentTaskFilter === "ACTIVE") return t.status === "ACTIVE" || t.status === "RUNNING";
      if (this.currentTaskFilter === "WAITING") return t.status === "WAITING" || t.status === "DEPENDENCY_WAIT";
      if (this.currentTaskFilter === "GATED") return t.status === "HUMAN_GATE" || t.status === "MONEY_GATE" || t.status === "BLOCKED";
      return true;
    });

    if (this.taskBoardCount) {
      this.taskBoardCount.textContent = `${this.lastTaskBoardData.length} TASKS`;
    }

    if (filtered.length === 0) {
      this.taskBoardCards.innerHTML = '<div class="text-muted font-mono" style="font-size: 8px; text-align: center; padding: 12px 0;">No tasks in this view (Organization Safely Idle)</div>';
      return;
    }

    this.taskBoardCards.innerHTML = filtered.map(t => {
      const st = t.status || 'UNKNOWN';
      const provider = t.provider || 'LOCAL_DETERMINISTIC';
      const owner = t.owner_agent || 'UNASSIGNED';
      const title = t.title || t.task_id;
      return `
        <div class="task-card">
          <div class="task-card-top">
            <span class="task-card-id font-mono">${t.task_id}</span>
            <span class="task-card-status ${st}">${st}</span>
          </div>
          <div class="task-card-title">${title}</div>
          <div class="task-card-meta">
            <span class="task-card-badge">${provider}</span>
            <span>👤 ${owner}</span>
          </div>
        </div>
      `;
    }).join('');

    // Bind click handlers for Task Inspector
    this.taskBoardCards.querySelectorAll(".task-card").forEach((card, idx) => {
      card.style.cursor = "pointer";
      card.addEventListener("click", () => {
        const taskObj = filtered[idx];
        if (taskObj) this.openTaskInspector(taskObj);
      });
    });
  }

  updateChiefAlertBar(stateData) {
    if (!this.chiefAlertStream) return;
    const alerts = resolveChiefAlerts(stateData);
    if (!alerts || alerts.length === 0) {
      this.chiefAlertStream.innerHTML = `<span class="chief-alert-pill pill-info">🟢 SAFE_IDLE • ALL SYSTEMS HEALTHY • 0 EUR SPEND • LIVE TELEMETRY</span>`;
      return;
    }

    this.chiefAlertStream.innerHTML = alerts.map(a => {
      const icon = a.severity === 'CRITICAL' ? '🚨' : (a.severity === 'WARNING' ? '⚠️' : '🟢');
      const pillClass = a.severity === 'CRITICAL' ? 'pill-critical' : (a.severity === 'WARNING' ? 'pill-warning' : 'pill-info');
      return `<span class="chief-alert-pill ${pillClass}">${icon} <b>${a.type}</b>: ${a.message} <small class="text-muted">(${a.timestamp})</small></span>`;
    }).join(" ");
  }

  openAgentInspector(agent) {
    if (!this.inspectorModalBackdrop || !this.inspectorModalBody) return;
    const detail = resolveAgentDetailData(agent, this.lastLiveState);
    const stateClass = `badge-state-${detail.state.toLowerCase().replace(/_/g, '-')}`;
    this.inspectorModalTitle.textContent = `🤖 AGENT DETAIL PANEL // ${detail.name}`;
    this.inspectorModalBody.innerHTML = `
      <div class="inspector-field">
        <span class="inspector-field-label">NAME & ROLE</span>
        <span class="inspector-field-val font-mono"><b class="text-white">${detail.name}</b> • ${detail.role}</span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">STATE</span>
        <span class="inspector-field-val"><span class="inspector-state-badge ${stateClass}">${detail.state}</span></span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">MISSION</span>
        <span class="inspector-field-val">${detail.mission}</span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">TASK</span>
        <span class="inspector-field-val">${detail.task}</span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">LAST MEANINGFUL PROGRESS</span>
        <span class="inspector-field-val font-mono">${detail.last_progress}</span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">STATE AGE</span>
        <span class="inspector-field-val font-mono">${detail.state_age}</span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">BLOCKED REASON</span>
        <span class="inspector-field-val text-orange">${detail.blocked_reason}</span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">PROVIDER & EXECUTION CLASS</span>
        <span class="inspector-field-val font-mono text-cyan">${detail.provider}</span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">HEAVY JOB SCOPE</span>
        <span class="inspector-field-val font-mono">${detail.heavy_job}</span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">RESULT ID</span>
        <span class="inspector-field-val font-mono text-muted">${detail.result_id}</span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">SPEECH / RECENT STATEMENT</span>
        <span class="inspector-field-val text-green">${agent.speech || 'SAFE_IDLE — Standby'}</span>
      </div>
    `;
    this.inspectorModalBackdrop.classList.remove("hidden");
  }

  openTaskInspector(task) {
    if (!this.inspectorModalBackdrop || !this.inspectorModalBody) return;
    this.inspectorModalTitle.textContent = `📋 TASK INSPECTOR // ${task.task_id}`;
    this.inspectorModalBody.innerHTML = `
      <div class="inspector-field">
        <span class="inspector-field-label">TASK ID</span>
        <span class="inspector-field-val font-mono">${task.task_id}</span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">TITLE / GOAL</span>
        <span class="inspector-field-val">${task.title || task.task_id}</span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">OWNER & PROVIDER</span>
        <span class="inspector-field-val">${task.owner_agent || 'UNASSIGNED'} • <b class="text-cyan">${task.provider || 'LOCAL_DETERMINISTIC'}</b></span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">STATUS</span>
        <span class="inspector-field-val">${task.status || 'UNKNOWN'}</span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">LATEST MEANINGFUL EVENT</span>
        <span class="inspector-field-val font-mono">${task.last_meaningful_event ? JSON.stringify(task.last_meaningful_event) : 'None recorded'}</span>
      </div>
    `;
    this.inspectorModalBackdrop.classList.remove("hidden");
  }

  closeInspectorModal() {
    this.inspectorModalBackdrop?.classList.add("hidden");
  }

  openTimelineModal() {
    if (!this.reportModalBackdrop || !this.reportModalBody) return;
    this.reportModalTitle.textContent = "📈 PRODUCTIVITY TIMELINE";
    const timeline = this.lastLiveState?.productivity_timeline || [];
    if (timeline.length === 0) {
      this.reportModalBody.innerHTML = '<div class="text-muted font-mono" style="text-align: center; padding: 20px;">No timeline events recorded</div>';
    } else {
      this.reportModalBody.innerHTML = timeline.slice().reverse().map(item => {
        const time = item.timestamp ? item.timestamp.split('T')[1]?.substring(0, 8) : '';
        const evType = item.event_type || 'EVENT';
        const cls = evType.includes('COMPLETED') ? 'COMPLETED' : (evType.includes('GATE') ? 'GATE' : (evType.includes('ANOMALY') ? 'ANOMALY' : ''));
        return `
          <div class="timeline-entry-row ${cls}">
            <span class="timeline-entry-time">${time}</span>
            <div class="timeline-entry-content">
              <span class="timeline-entry-title">${evType} (${item.actor || 'SYSTEM'})</span>
              <span class="timeline-entry-desc">${item.details || item.task_id}</span>
            </div>
          </div>
        `;
      }).join('');
    }
    this.reportModalBackdrop.classList.remove("hidden");
  }

  openMorningReportModal() {
    if (!this.reportModalBackdrop || !this.reportModalBody) return;
    this.reportModalTitle.textContent = "🌅 MORNING / SESSION REPORT";
    const report = this.lastLiveState?.morning_report || {};
    const autoRuntime = this.lastLiveState?.autonomy_runtime || {};
    const endurance = this.lastLiveState?.endurance_188g || {};

    const completed = autoRuntime.jobs_completed || [];
    const humanGates = autoRuntime.human_gates || [];
    const moneyGates = autoRuntime.money_gates || [];

    this.reportModalBody.innerHTML = `
      <div class="inspector-field">
        <span class="inspector-field-label">SESSION GOAL</span>
        <span class="inspector-field-val text-cyan">${autoRuntime.current_goal || 'Autonomous Operations'}</span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">188G ENDURANCE PROGRESS</span>
        <span class="inspector-field-val text-green">${endurance.status || 'PENDING'} • ${(endurance.elapsed_seconds || 0) / 3600 | 0}h / ${endurance.duration_target_hours || 8}h (${endurance.model_calls_during_idle || 0} idle model calls)</span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">TASKS COMPLETED (${completed.length})</span>
        <span class="inspector-field-val">${completed.length > 0 ? (typeof completed[0] === 'string' ? completed.join(', ') : completed.map(c => c.task_id || JSON.stringify(c)).join(', ')) : 'None yet'}</span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">GATES ENCOUNTERED</span>
        <span class="inspector-field-val">${humanGates.length} Human Gate(s) • ${moneyGates.length} Money Gate(s) (0 EUR Spend Limit Maintained)</span>
      </div>
      <div class="inspector-field">
        <span class="inspector-field-label">RECOMMENDED NEXT ACTION</span>
        <span class="inspector-field-val">Continue unattended operations in safe idle standby</span>
      </div>
    `;
    this.reportModalBackdrop.classList.remove("hidden");
  }

  closeReportModal() {
    this.reportModalBackdrop?.classList.add("hidden");
  }

  syncAgentSimulations(agents) {
    for (const agent of agents) {
      let sim = this.agentSims.get(agent.id);

      if (!sim) {
        sim = {
          id: agent.id,
          currentX: agent.x,
          currentY: agent.y,
          targetX: agent.x,
          targetY: agent.y,
          homeX: agent.homeX || agent.x,
          homeY: agent.homeY || agent.y,
          pathQueue: [],
          isWalking: false,
          facing: 1,
        };
        this.agentSims.set(agent.id, sim);
      }
    }
  }

  renderLivingAgents(agents, motion = null) {
    if (!this.agentsLayer) return;

    const seenIds = new Set();

    agents.forEach(agent => {
      seenIds.add(agent.id);
      let node = this.agentNodes.get(agent.id);

      if (!node) {
        node = document.createElement("div");
        node.className = "living-agent-node";
        node.id = `node-${agent.id}`;
        node.style.cursor = "pointer";
        node.addEventListener("click", (e) => {
          e.stopPropagation();
          // Primary interaction: lower operations bay. Modal only via ADVANCED DETAILS.
          const live = this.lastAgents?.find(a => a.id === agent.id) || agent;
          selectAgent(agent.id, { name: live.name, title: live.title || live.role, icon: live.icon });
        });

        node.addEventListener("mouseenter", () => {
          this.hoveredAgentId = agent.id;
          node.classList.add("is-hovered");
          const bubble = node.querySelector(".agent-speech-bubble");
          if (bubble && bubble.textContent.trim()) {
            bubble.style.display = "block";
            bubble.classList.add("speech-hovered");
          }
        });

        node.addEventListener("mouseleave", () => {
          if (this.hoveredAgentId === agent.id) {
            this.hoveredAgentId = null;
          }
          node.classList.remove("is-hovered");
          const bubble = node.querySelector(".agent-speech-bubble");
          if (bubble) {
            bubble.classList.remove("speech-hovered");
            const mState = motion?.states?.[agent.id] || agent.state;
            const nState = (mState || agent.state || "UNKNOWN").toUpperCase();
            const sOverride = motion?.speech_overrides?.[agent.id];
            const isActOrProb = nState === "PROGRESSING" || nState === "RUNNING" || nState === "WORKING" ||
                                nState === "WAITING_HUMAN" || nState === "WAITING_PERMISSION" ||
                                nState === "HUNG" || nState === "PROVIDER_ERROR" ||
                                nState === "ORPHANED" || nState === "RUNNING_NO_PROGRESS" ||
                                Boolean(sOverride);
            if (this.speechMode === "ALL" || (this.speechMode === "SMART" && isActOrProb)) {
              bubble.style.display = "block";
            } else {
              bubble.style.display = "none";
            }
          }
        });
        
        const nameplate = document.createElement("div");
        nameplate.className = "agent-nameplate";
        const title = document.createElement("span");
        title.className = "nameplate-title";
        title.textContent = agent.name || "UNKNOWN";
        const subtitle = document.createElement("span");
        subtitle.className = "nameplate-subtitle";
        subtitle.textContent = agent.title || "UNKNOWN";
        nameplate.append(title, subtitle);

        const avatar = document.createElement("div");
        avatar.className = "agent-avatar-body";
        const iconSymbol = agent.icon || (agent.is_bodyguard ? "🛡️" : (AVATAR_ICONS[agent.id] || "🤖"));
        const avatarIcon = document.createElement("span");
        avatarIcon.className = "avatar-icon";
        avatarIcon.textContent = iconSymbol;
        const avatarRing = document.createElement("span");
        avatarRing.className = "avatar-status-ring";
        avatar.append(avatarIcon, avatarRing);

        const speech = document.createElement("div");
        speech.className = "agent-speech-bubble";
        speech.style.display = "none";

        node.appendChild(nameplate);
        node.appendChild(avatar);
        node.appendChild(speech);

        // Stable placement: appear directly at canonical coords, fade only.
        if (agent.x != null) node.style.left = `${agent.x}%`;
        if (agent.y != null) node.style.top = `${agent.y}%`;
        node.dataset.spawnPending = "1";
        this.agentsLayer.appendChild(node);
        this.agentNodes.set(agent.id, node);
      }

      // State Classes & Visual Indicators
      // Fade-in runs exactly once per node lifetime; positions are preset so
      // nothing travels across the map on reload.
      node.className = "living-agent-node" + (node.dataset.spawnPending ? " is-spawn" : "");
      delete node.dataset.spawnPending;
      if (this.hoveredAgentId === agent.id) node.classList.add("is-hovered");
      const motionState = motion?.states?.[agent.id] || agent.state;
      const normalizedState = (motionState || agent.state || "UNKNOWN").toUpperCase();

      // Apply distinct classes for all 11 states
      if (normalizedState === "PROGRESSING" || normalizedState === "RUNNING" || normalizedState === "WORKING") {
        node.classList.add("state-progressing", "state-working");
      } else if (normalizedState === "SAFE_IDLE" || normalizedState === "AVAILABLE" || normalizedState === "STANDBY" || normalizedState === "IDLE") {
        node.classList.add("state-safe-idle");
      } else if (normalizedState === "WAITING_PERMISSION") {
        node.classList.add("state-waiting-permission", "state-blocked");
      } else if (normalizedState === "WAITING_HUMAN" || normalizedState === "HUMAN_GATE") {
        node.classList.add("state-waiting-human", "state-blocked");
      } else if (normalizedState === "RUNNING_NO_PROGRESS") {
        node.classList.add("state-running-no-progress");
      } else if (normalizedState === "HUNG") {
        node.classList.add("state-hung", "state-blocked");
      } else if (normalizedState === "PROVIDER_ERROR") {
        node.classList.add("state-provider-error", "state-blocked");
      } else if (normalizedState === "NETWORK_DEGRADED") {
        node.classList.add("state-network-degraded");
      } else if (normalizedState === "COMPLETED") {
        node.classList.add("state-completed");
      } else if (normalizedState === "ORPHANED") {
        node.classList.add("state-orphaned", "state-blocked");
      } else {
        node.classList.add("state-unknown");
      }

      if (agent.is_bodyguard) node.classList.add("is-bodyguard");

      // Render relaxation/duty prop on avatar body
      let propEl = node.querySelector(".agent-prop");
      if (agent.prop) {
        if (!propEl) {
          propEl = document.createElement("span");
          propEl.className = `agent-prop prop-${agent.prop}`;
          const avatarBody = node.querySelector(".agent-avatar-body");
          if (avatarBody) avatarBody.appendChild(propEl);
        }
        propEl.className = `agent-prop prop-${agent.prop}`;
        propEl.textContent = agent.prop === "cigarette" ? "🚬" : (agent.prop === "shisha" ? "🏺💨" : "🍹");
        propEl.style.display = "inline-block";
      } else if (propEl) {
        propEl.style.display = "none";
      }

      // Initial coordinates if not yet positioned
      if (!node.style.left) {
        node.style.left = `${agent.x.toFixed(2)}%`;
        node.style.top = `${agent.y.toFixed(2)}%`;
      }

      // Update Subtitle / State Indicator
      const subtitle = node.querySelector(".nameplate-subtitle");
      if (subtitle) subtitle.textContent = agent.display_state || normalizedState;

      // Smart Speech Bubble Visibility: Uncluttered by default
      const speechEl = node.querySelector(".agent-speech-bubble");
      if (speechEl) {
        const speechOverride = motion?.speech_overrides?.[agent.id];
        const speechText = speechOverride || agent.speech;
        if (speechText && speechText.trim()) {
          speechEl.textContent = speechText;

          const isHovered = (this.hoveredAgentId === agent.id);
          const isActiveOrProblem = normalizedState === "PROGRESSING" || normalizedState === "RUNNING" || normalizedState === "WORKING" ||
                                    normalizedState === "WAITING_HUMAN" || normalizedState === "WAITING_PERMISSION" ||
                                    normalizedState === "HUNG" || normalizedState === "PROVIDER_ERROR" ||
                                    normalizedState === "ORPHANED" || normalizedState === "RUNNING_NO_PROGRESS" ||
                                    Boolean(speechOverride);

          if (this.speechMode === "ALL") {
            speechEl.style.display = "block";
          } else if (this.speechMode === "SMART" && (isActiveOrProblem || isHovered)) {
            speechEl.style.display = "block";
          } else if (this.speechMode === "ZEN" && isHovered) {
            speechEl.style.display = "block";
          } else {
            speechEl.style.display = "none";
          }
        } else {
          speechEl.style.display = "none";
        }
      }
    });

    // Remove any stale agents
    for (const [id, node] of this.agentNodes.entries()) {
      if (!seenIds.has(id)) {
        node.remove();
        this.agentNodes.delete(id);
        this.agentSims.delete(id);
      }
    }
  }

  updateCourierTransport(agents, stateData, motion = null) {
    if (!this.courierPacket) return;

    const courierSim = this.agentSims.get("agent-courier-relay");
    const courierPhase = motion?.courier_phase || resolveLiveOrchestrationTruth(stateData).courier_phase;
    const isHandoff = motion?.states?.["agent-courier-relay"] === "HANDOFF";

    if (courierSim && (courierPhase === "TASK_DELIVERY" || courierPhase === "RESULT_RETURN" || isHandoff)) {
      this.courierPacket.style.display = "flex";
      this.courierPacket.style.left = `${(courierSim.currentX + 2.0).toFixed(2)}%`;
      this.courierPacket.style.top = `${(courierSim.currentY - 3.5).toFixed(2)}%`;

      if (isHandoff) {
        this.courierPacket.className = "courier-transport-packet packet-task";
        if (this.courierPacketLabel) this.courierPacketLabel.textContent = "HANDOFF";
      } else if (courierPhase === "RESULT_RETURN") {
        this.courierPacket.className = "courier-transport-packet packet-result";
        if (this.courierPacketLabel) this.courierPacketLabel.textContent = "RESULT";
      } else {
        this.courierPacket.className = "courier-transport-packet packet-task";
        if (this.courierPacketLabel) this.courierPacketLabel.textContent = "TASK";
      }
    } else {
      this.courierPacket.style.display = "none";
    }
  }

  updateTelemetryAndGate(stateData, metrics) {
    // 1. SNITCH 3.0 Guard
    const perm = resolvePermissionGuardTruth(stateData);
    if (this.snitchPermStatus) {
      this.snitchPermStatus.textContent = perm.policy_status || "HEALTHY";
      this.snitchPermStatus.className = perm.is_healthy ? "badge-perm-healthy text-green" : "badge-perm-alert text-red";
    }
    if (this.snitchPermCommand) this.snitchPermCommand.textContent = perm.active_command || "NONE";
    if (this.snitchPermRuleRec) this.snitchPermRuleRec.textContent = perm.matched_rule || "ALREADY_ALLOWED";

    // 2. Live Workflow
    if (this.liveWfId) this.liveWfId.textContent = metrics.current_workflow || "NONE";
    const wfStatusText = metrics.is_flow_active ? `IN_PROGRESS (${Math.round((metrics.active_agents / 40) * 100)}%)` : "IDLE_MONITORING";
    if (this.liveWfStatus) this.liveWfStatus.textContent = wfStatusText;
    if (this.liveWfBar) this.liveWfBar.style.width = metrics.is_flow_active ? `${Math.max(15, (metrics.active_agents / 40) * 100)}%` : "0%";

    // 3. Treasury Truth
    const econ = resolveAcademyEconomics(stateData);
    if (this.treasuryEur) this.treasuryEur.textContent = econ.verified_eur || "UNKNOWN";
    if (this.treasuryUsd) this.treasuryUsd.textContent = econ.verified_usd || "UNAVAILABLE";
    if (this.treasuryVerified) this.treasuryVerified.textContent = econ.evidence_status || "NOT_VERIFIED";
    if (this.treasuryGoal) this.treasuryGoal.textContent = econ.goal_display || "$8 GOAL";

    // 4. Repositories & Context
    if (this.panelCtxVer) this.panelCtxVer.textContent = metrics.context_version ? `v${metrics.context_version}` : "UNKNOWN";
    if (this.panelCtxPrev) this.panelCtxPrev.textContent = metrics.prev_version ? `v${metrics.prev_version}` : "UNKNOWN";
    if (this.panelCtxHash) this.panelCtxHash.textContent = metrics.context_hash ? `${metrics.context_hash.slice(0, 12)}...` : "UNAVAILABLE";
    if (this.courierCommitTag) this.courierCommitTag.textContent = `HEAD: ${metrics.courier_commit || "UNAVAILABLE"}`;
    if (this.panelRepoCourier) this.panelRepoCourier.textContent = metrics.courier_commit || "UNAVAILABLE";
    if (this.panelRepoMemory) this.panelRepoMemory.textContent = metrics.memory_commit || "UNAVAILABLE";

    // 5. Human Gate Alert Banner
    const gate = resolveActiveGateTruth(stateData);
    this.currentGate = gate;
    if (this.gateBanner && this.gateDesc) {
      if (gate && gate.is_active) {
        this.gateBanner.classList.remove("hidden");
        this.gateDesc.textContent = gate.description || "A workflow task or policy alert requires human sign-off.";
      } else {
        this.gateBanner.classList.add("hidden");
      }
    }
  }

  async dispatchHumanIdea() {
    const idea = this.humanIdeaInput?.value?.trim();
    if (!idea) return;

    try {
      this.btnDispatchIdea.disabled = true;
      this.btnDispatchIdea.textContent = "SYNCING CONTEXT...";
      const res = await fetch("/api/human-dispatch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idea, mode: "AUTONOMOUS" }),
      });
      if (res.ok) {
        this.humanIdeaInput.value = "";
        this.drawer?.classList.add("hidden");
      }
    } catch (e) {
      console.error("Dispatch idea failed:", e);
    } finally {
      this.btnDispatchIdea.disabled = false;
      this.btnDispatchIdea.innerHTML = `<span class="dispatch-icon">⚡</span> DISPATCH DIRECTIVE`;
    }
  }

  async sendGateDecision(approve) {
    if (!this.currentGate) return;
    try {
      await fetch("/api/human-decision", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          gate_id: this.currentGate.id,
          decision: approve ? "APPROVED" : "REJECTED",
        }),
      });
      if (this.gateBanner) this.gateBanner.classList.add("hidden");
    } catch (e) {
      console.error("Gate decision failed:", e);
    }
  }
}

// Bootstrap Robustly
function bootstrapStudio() {
  if (!window.livingHQ) {
    window.livingHQ = new LivingHQController();
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootstrapStudio);
} else {
  bootstrapStudio();
}
