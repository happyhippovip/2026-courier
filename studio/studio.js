/**
 * 2026 Courier // Autonomous Chief Operations Cockpit Controller
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
    // Controls & Inbox
    this.btn16x9 = document.getElementById('btn-aspect-16-9');
    this.btn9x16 = document.getElementById('btn-aspect-9-16');
    this.btnRecord = document.getElementById('btn-recording-mode');
    this.ideaInput = document.getElementById('human-idea-input');
    this.btnDispatchIdea = document.getElementById('btn-dispatch-idea');
    this.presetBtns = document.querySelectorAll('.preset-btn');

    // Human Gate Banner
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

    // Antigravity Elements
    this.badgeAgMode = document.getElementById('badge-ag-mode');
    this.agState = document.getElementById('ag-state');
    this.agTaskLabel = document.getElementById('ag-task-label');
    this.agProgressNum = document.getElementById('ag-progress-num');
    this.agProgressBar = document.getElementById('ag-progress-bar');
    this.agFeedLog = document.getElementById('ag-feed-log');

    // Codex Elements
    this.badgeCodexMode = document.getElementById('badge-codex-mode');
    this.codexState = document.getElementById('codex-state');
    this.codexTaskLabel = document.getElementById('codex-task-label');
    this.codexProgressNum = document.getElementById('codex-progress-num');
    this.codexProgressBar = document.getElementById('codex-progress-bar');
    this.codexFeedLog = document.getElementById('codex-feed-log');

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

    this.presetBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const idea = btn.getAttribute('data-idea');
        this.ideaInput.value = idea;
      });
    });

    this.btnDispatchIdea.addEventListener('click', () => this.submitHumanIdea());
    this.ideaInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.submitHumanIdea();
    });

    this.btnGateApprove.addEventListener('click', () => {
      this.gateBanner.classList.add('hidden');
    });

    this.btnGateReject.addEventListener('click', () => {
      this.gateBanner.classList.add('hidden');
    });
  }

  async submitHumanIdea() {
    const idea = this.ideaInput.value.trim();
    if (!idea) return;

    try {
      this.btnDispatchIdea.disabled = true;
      this.btnDispatchIdea.innerHTML = '<span class="dispatch-icon">⏳</span> ROUTING...';
      
      this.appendLog(this.chiefFeedLog, `[HUMAN IDEA] ${idea}`);

      const res = await fetch('/api/submit-idea', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idea: idea, type: 'IDEA' }),
      });

      const data = await res.json();
      console.log('Idea submitted to Chief:', data);
      this.ideaInput.value = '';
    } catch (err) {
      console.error('Failed to submit idea:', err);
    } finally {
      setTimeout(() => {
        this.btnDispatchIdea.disabled = false;
        this.btnDispatchIdea.innerHTML = '<span class="dispatch-icon">⚡</span> DISPATCH TO CHIEF';
      }, 1500);
    }
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

    // 2. Update Chief Station
    const chief = agents['agent-chief-commander'] || {};
    const chiefState = chief.state || (bus.is_locked ? 'COORDINATING' : 'IDLE');
    this.badgeChiefState.textContent = chiefState;
    this.chiefWorkflow.textContent = chief.workflow || bus.active_workflow || '-';
    this.chiefLastDecision.textContent = bus.last_decision || 'ACCEPTED';
    this.chiefTaskLabel.textContent = chief.task ? `Task: ${chief.task}` : 'Task: Standby';
    const chiefProgress = Math.round((chief.progress || 0) * 100);
    this.chiefProgressNum.textContent = `${chiefProgress}%`;
    this.chiefProgressBar.style.width = `${chiefProgress}%`;

    if (chief.last_action) {
      this.appendLog(this.chiefFeedLog, `[CHIEF] ${chief.last_action}`);
    }

    const chiefCard = document.getElementById('station-chief');
    if (chiefState === 'RUNNING' || chiefState === 'COORDINATING') {
      chiefCard.classList.add('active-working');
    } else {
      chiefCard.classList.remove('active-working');
    }

    // 3. Update Antigravity Station (Primary Heavy Worker)
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

    // 4. Update Codex Station (Scarce Technical Specialist)
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

    // 5. Human Gate Alert Banner
    if (chief.state === 'BLOCKED_HUMAN_GATE' || codex.state === 'BLOCKED_HUMAN_GATE' || ag.state === 'BLOCKED_HUMAN_GATE' || bus.human_gate) {
      this.gateBanner.classList.remove('hidden');
      this.gateDesc.textContent = `Workflow task paused: ${codex.task || ag.task || chief.task || 'Explicit human approval required'}`;
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
