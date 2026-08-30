/**
 * 2026 Courier // Visual Multi-Agent Operations Studio Frontend Engine
 */

class OperationsStudio {
  constructor() {
    this.pollInterval = 500;
    this.isPolling = false;
    this.initElements();
    this.bindEvents();
    this.startPolling();
  }

  initElements() {
    // Buttons & Controls
    this.btn16x9 = document.getElementById('btn-aspect-16-9');
    this.btn9x16 = document.getElementById('btn-aspect-9-16');
    this.btnRecord = document.getElementById('btn-recording-mode');
    this.btnTrigger = document.getElementById('btn-trigger-demo');
    this.gateBanner = document.getElementById('human-gate-banner');
    this.gateDesc = document.getElementById('gate-desc');
    this.btnGateApprove = document.getElementById('btn-gate-approve');
    this.btnGateReject = document.getElementById('btn-gate-reject');

    // Chief Elements
    this.badgeChiefState = document.getElementById('badge-chief-state');
    this.chiefWorkflow = document.getElementById('chief-workflow');
    this.chiefLastDecision = document.getElementById('chief-last-decision');
    this.chiefTaskLabel = document.getElementById('chief-task-label');
    this.chiefProgressNum = document.getElementById('chief-progress-num');
    this.chiefProgressBar = document.getElementById('chief-progress-bar');
    this.chiefFeedLog = document.getElementById('chief-feed-log');

    // Courier Bus Elements
    this.badgeBusState = document.getElementById('badge-bus-state');
    this.countDispatch = document.getElementById('count-dispatch');
    this.countProcessed = document.getElementById('count-processed');
    this.countDecisions = document.getElementById('count-decisions');
    this.busLockStatus = document.getElementById('bus-lock-status');
    this.busCorrId = document.getElementById('bus-corr-id');

    // Codex Elements
    this.badgeCodexMode = document.getElementById('badge-codex-mode');
    this.codexBackendName = document.getElementById('codex-backend-name');
    this.codexState = document.getElementById('codex-state');
    this.codexTaskLabel = document.getElementById('codex-task-label');
    this.codexProgressNum = document.getElementById('codex-progress-num');
    this.codexProgressBar = document.getElementById('codex-progress-bar');
    this.codexFeedLog = document.getElementById('codex-feed-log');

    // Antigravity Elements
    this.badgeAgMode = document.getElementById('badge-ag-mode');
    this.agState = document.getElementById('ag-state');
    this.agTaskLabel = document.getElementById('ag-task-label');
    this.agProgressNum = document.getElementById('ag-progress-num');
    this.agProgressBar = document.getElementById('ag-progress-bar');
    this.agFeedLog = document.getElementById('ag-feed-log');

    // Footer
    this.lastPollTime = document.getElementById('last-poll-time');
    this.serverStatus = document.getElementById('server-status');
  }

  bindEvents() {
    this.btn16x9.addEventListener('click', () => {
      document.body.classList.remove('view-9-16');
      this.btn16x9.classList.add('active');
      this.btn9x16.classList.remove('active');
    });

    this.btn9x16.addEventListener('click', () => {
      document.body.classList.add('view-9-16');
      this.btn9x16.classList.add('active');
      this.btn16x9.classList.remove('active');
    });

    this.btnRecord.addEventListener('click', () => {
      document.body.classList.toggle('recording-mode');
    });

    this.btnTrigger.addEventListener('click', async () => {
      try {
        this.btnTrigger.disabled = true;
        this.btnTrigger.textContent = 'RUNNING...';
        const res = await fetch('/api/trigger-workflow', { method: 'POST' });
        const data = await res.json();
        console.log('Workflow triggered:', data);
      } catch (err) {
        console.error('Trigger failed:', err);
      } finally {
        setTimeout(() => {
          this.btnTrigger.disabled = false;
          this.btnTrigger.innerHTML = '<span class="play-icon">▶</span> RUN MULTI-AGENT LOOP';
        }, 2000);
      }
    });

    this.btnGateApprove.addEventListener('click', () => {
      this.gateBanner.classList.add('hidden');
    });

    this.btnGateReject.addEventListener('click', () => {
      this.gateBanner.classList.add('hidden');
    });
  }

  startPolling() {
    this.isPolling = true;
    this.poll();
  }

  async poll() {
    try {
      const response = await fetch('/api/state');
      if (response.ok) {
        const state = await response.json();
        this.updateUI(state);
        this.serverStatus.textContent = 'LIVE BUS CONNECTED';
        this.serverStatus.style.color = 'var(--text-primary)';
      } else {
        this.serverStatus.textContent = 'BUS DISCONNECTED';
        this.serverStatus.style.color = 'var(--accent-red)';
      }
    } catch (err) {
      this.serverStatus.textContent = 'STANDALONE OFFLINE';
      this.serverStatus.style.color = 'var(--text-muted)';
    }

    const now = new Date();
    this.lastPollTime.textContent = now.toTimeString().split(' ')[0];

    if (this.isPolling) {
      setTimeout(() => this.poll(), this.pollInterval);
    }
  }

  updateUI(data) {
    if (!data) return;

    const { agents = {}, counts = {}, bus = {} } = data;

    // 1. Update Bus Counts
    this.countDispatch.textContent = counts.dispatch || 0;
    this.countProcessed.textContent = counts.processed || 0;
    this.countDecisions.textContent = counts.decisions || 0;
    this.busLockStatus.textContent = bus.is_locked ? `LOCKED (${bus.active_lock})` : 'UNLOCKED';
    this.busCorrId.textContent = bus.correlation_id || '-';

    // 2. Update Codex Station
    const codex = agents['agent-codex-bridge'] || {};
    this.codexState.textContent = codex.state || 'IDLE';
    this.codexTaskLabel.textContent = codex.task ? `Task: ${codex.task}` : 'Task: IDLE';
    const cdxProgress = Math.round((codex.progress || 0) * 100);
    this.codexProgressNum.textContent = `${cdxProgress}%`;
    this.codexProgressBar.style.width = `${cdxProgress}%`;

    if (codex.last_action) {
      this.appendLog(this.codexFeedLog, `[CODEX] ${codex.last_action}`);
    }

    const codexCard = document.getElementById('station-codex');
    if (codex.state === 'RUNNING') {
      codexCard.classList.add('active-working');
    } else {
      codexCard.classList.remove('active-working');
    }

    // Worker mode identification
    if (codex.result && codex.result.agent_source === 'CODEX_CLI_REAL') {
      this.badgeCodexMode.textContent = '🟢 REAL CODEX CLI';
      this.badgeCodexMode.style.borderColor = 'var(--accent-green)';
      this.badgeCodexMode.style.color = 'var(--accent-green)';
    } else {
      this.badgeCodexMode.textContent = '🟡 DUAL HYBRID (CLI / CLASS B)';
    }

    // 3. Update Antigravity Station
    const ag = agents['agent-antigravity-bridge'] || {};
    this.agState.textContent = ag.state || 'IDLE';
    this.agTaskLabel.textContent = ag.task ? `Task: ${ag.task}` : 'Task: IDLE';
    const agProgress = Math.round((ag.progress || 0) * 100);
    this.agProgressNum.textContent = `${agProgress}%`;
    this.agProgressBar.style.width = `${agProgress}%`;

    if (ag.last_action) {
      this.appendLog(this.agFeedLog, `[AG] ${ag.last_action}`);
    }

    const agCard = document.getElementById('station-antigravity');
    if (ag.state === 'RUNNING') {
      agCard.classList.add('active-working');
    } else {
      agCard.classList.remove('active-working');
    }

    // 4. Update Chief Station
    const chiefState = (codex.state === 'RUNNING' || ag.state === 'RUNNING') ? 'COORDINATING' : 'IDLE';
    this.badgeChiefState.textContent = chiefState;
    this.chiefWorkflow.textContent = codex.workflow || ag.workflow || bus.active_workflow || '-';
    this.chiefLastDecision.textContent = bus.last_decision || 'ACCEPTED';

    const chiefCard = document.getElementById('station-chief');
    if (chiefState === 'COORDINATING') {
      chiefCard.classList.add('active-working');
    } else {
      chiefCard.classList.remove('active-working');
    }

    // 5. Human Gate Alert Banner Check
    if (codex.state === 'BLOCKED_HUMAN_GATE' || ag.state === 'BLOCKED_HUMAN_GATE' || bus.human_gate) {
      this.gateBanner.classList.remove('hidden');
      this.gateDesc.textContent = `Workflow task paused: ${codex.task || ag.task || 'Publication stage requires human approval'}`;
    } else {
      this.gateBanner.classList.add('hidden');
    }
  }

  appendLog(feedElement, text) {
    if (!feedElement) return;
    const lastEntry = feedElement.lastElementChild;
    if (lastEntry && lastEntry.textContent === text) return;

    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.textContent = text;
    feedElement.appendChild(entry);
    feedElement.scrollTop = feedElement.scrollHeight;
  }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  window.studio = new OperationsStudio();
});
