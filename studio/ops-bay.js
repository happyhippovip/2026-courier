// LIVE OPERATIONS BAY controller. Observational only: renders the selected
// agent from the shared ops_state snapshot. Never fabricates activity, never
// mutates Ledger/Motor, never touches the network. All dynamic text is set
// via textContent (no HTML injection from telemetry).
const STORAGE_KEY = 'courier.opsBay.agent';
const META = {
  muse: { name: 'MUSE', role: 'MAIN WORKER', icon: '∞' },
  codex: { name: 'CODEX', role: 'QA SPECIALIST', icon: '💬' },
  google: { name: 'GOOGLE', role: 'PRO BUILDER', icon: '✦' },
};

function el(id) { return document.getElementById(id); }
function setText(id, v) { const n = el(id); if (n) n.textContent = v ?? '—'; }

function fmtAge(iso) {
  const t = Date.parse(iso || '');
  if (!Number.isFinite(t)) return 'UNKNOWN';
  const s = Math.max(0, Math.round((Date.now() - t) / 1000));
  return s < 5 ? 'jetzt' : s < 60 ? `${s}s her` : `${Math.floor(s / 60)}m her`;
}

function taskText(opsAgent) {
  if (opsAgent?.task) return opsAgent.task;
  if (opsAgent?.state === 'ACTIVE')
    return 'Lokale Aktivität erkannt — konkrete Aufgabe nicht gemeldet';
  return 'Keine konkrete Aufgabe gemeldet';
}

function recentEvents(stateData, agentId, max = 8) {
  const out = [];
  const feed = stateData?.result_feed;
  if (Array.isArray(feed)) {
    for (const ev of feed.slice(-24)) {
      const txt = typeof ev === 'string' ? ev : (ev?.title || ev?.task_id || ev?.kind || '');
      const who = typeof ev === 'object' ? (ev?.agent || ev?.owner_agent || '') : '';
      if (!txt) continue;
      if (agentId && who && !String(who).toLowerCase().includes(agentId)) continue;
      const ts = (ev?.ingested_at || ev?.timestamp || '').slice(11, 19) || '??:??:??';
      out.push(`${ts}  ${String(txt).slice(0, 90)}`);
      if (out.length >= max) break;
    }
  }
  return out;
}

const host = {
  selectedAgent: null,
  selectedAt: 0,
  lastOps: null,
  lastState: null,
  openAdvanced: null, // wired by studio.js (modal fallback)
};

export function initOpsBay(callbacks = {}) {
  host.openAdvanced = callbacks.openAdvanced || null;
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && META[saved]) { host.selectedAgent = saved; host.selectedAt = Date.now(); }
  } catch { /* storage unavailable: selection simply won't survive refresh */ }
  el('ops-bay-close')?.addEventListener('click', () => selectAgent(null));
  el('ops-bay-adv')?.addEventListener('click', () => {
    if (host.selectedAgent && host.openAdvanced) host.openAdvanced(host.selectedAgent);
  });
}

export function selectAgent(id, agent) {
  host.selectedAgent = (id && (META[id] || agent)) ? id : null;
  host.selectedMeta = (id && agent) ? agent : null;
  host.selectedAt = host.selectedAgent ? Date.now() : 0;
  try {
    if (host.selectedAgent) localStorage.setItem(STORAGE_KEY, host.selectedAgent);
    else localStorage.removeItem(STORAGE_KEY);
  } catch { /* ignore */ }
  renderOpsBay();
}

export function getSelectedAgent() { return host.selectedAgent; }

export function renderOpsBay(opsState, stateData) {
  if (opsState) host.lastOps = opsState;
  if (stateData) host.lastState = stateData;
  const bay = el('ops-bay');
  if (!bay) return;
  const id = host.selectedAgent;
  const idle = el('ops-bay-idle');
  const live = el('ops-bay-live');
  const meta = META[id] || (host.selectedMeta
    ? { name: host.selectedMeta.name || id, role: host.selectedMeta.title || host.selectedMeta.role || 'OPERATOR', icon: host.selectedMeta.icon || '◌' }
    : null);
  if (!id || !meta) {
    bay.classList.add('is-collapsed');
    if (idle) idle.hidden = false;
    if (live) live.hidden = true;
    return;
  }
  bay.classList.remove('is-collapsed');
  if (idle) idle.hidden = true;
  if (live) live.hidden = false;
  const m = meta;
  const opsId = id === 'local-tool-muse' || id === 'muse' ? 'muse'
    : id === 'local-tool-chatgpt' || id === 'worker-codex' || id === 'codex' ? 'codex'
    : id === 'local-tool-antigravity' || id === 'worker-google' || id === 'google' ? 'google' : null;
  const oa = (opsId && host.lastOps?.agents?.[opsId]) || null;
  const st = host.lastState || {};
  const auto = st.autonomy_runtime || {};
  const ledger = st.courier_ledger || {};
  const local = st.local_tools || null;

  setText('ops-bay-icon', m.icon);
  setText('ops-bay-name', m.name);
  setText('ops-bay-role', `${m.role} // MACBOOK`);
  const stateEl = el('ops-bay-state');
  const state = oa?.state || 'UNKNOWN';
  if (stateEl) {
    stateEl.textContent = state === 'ACTIVE' ? '● ACTIVE' : state === 'IDLE' ? '○ IDLE'
      : state === 'WAITING' ? '◌ WAITING' : state === 'BLOCKED' ? '! BLOCKED'
      : state === 'OFFLINE' ? '× OFFLINE' : state === 'ERROR' ? '! ERROR' : '? UNKNOWN';
    stateEl.dataset.opsState = state;
  }
  const elapsed = host.selectedAt ? Math.floor((Date.now() - host.selectedAt) / 1000) : 0;
  setText('ops-bay-elapsed', elapsed > 0 ? `${elapsed}s` : '');
  setText('ops-bay-src', oa?.source ? `QUELLE: ${oa.source}` : '');
  setText('ops-bay-mission', auto.current_goal || 'Keine aktive Mission gemeldet');
  const taskNode = el('ops-bay-task');
  if (taskNode) {
    taskNode.textContent = taskText(oa);
    taskNode.parentElement?.classList.toggle('is-long', taskNode.textContent.length > 90);
    taskNode.closest('.ops-bay-task')?.classList.toggle('is-active', state === 'ACTIVE');
  }
  setText('ops-bay-step', auto.current_action && auto.current_action !== 'IDLE_EXPECTED' ? auto.current_action : '—');
  setText('ops-bay-file', 'UNKNOWN');
  setText('ops-bay-test', 'UNKNOWN');
  const feed = recentEvents(host.lastState, id, 1);
  setText('ops-bay-action', feed.length ? feed[0].slice(10) : '—');
  setText('ops-bay-blocker', auto.human_gates?.[0] || auto.money_gates?.[0] || 'NONE');
  setText('ops-bay-hb', local?.observed_at ? fmtAge(local.observed_at) : 'UNKNOWN');

  const pipe = el('ops-bay-pipe');
  if (pipe) {
    const stages = ['DISCOVER', 'READ', 'ATTACK', 'REPAIR', 'TEST', 'VERIFY', 'COMMIT'];
    pipe.textContent = stages.join(' → ');
    pipe.dataset.opsState = state;
  }
  const hist = el('ops-bay-hist');
  if (hist) {
    const evs = recentEvents(host.lastState, id, 8);
    hist.textContent = evs.length ? evs.join('\n') : 'Keine Ereignisse gemeldet';
  }
  const tech = el('ops-bay-techgrid');
  if (tech) {
    const rows = [
      ['HEAD', (st.repo_head_sha || 'UNKNOWN').slice(0, 12)],
      ['LEDGER', `${ledger.status ?? 'UNKNOWN'} · rev ${ledger.revision ?? '?'}`],
      ['GUARD', ledger.guard ?? 'UNKNOWN'],
      ['NEXT', ledger.next_action ?? 'UNKNOWN'],
      ['UNPROVEN', ledger.unproven_count ?? 'UNKNOWN'],
      ['PID', 'UNKNOWN'], ['PPID', 'UNKNOWN'], ['WORKTREE', 'UNKNOWN'],
      ['BRANCH', 'release-candidate-integration'],
      ['HEARTBEAT', local?.observed_at ? fmtAge(local.observed_at) : 'UNKNOWN'],
      ['DATENQUELLE', oa?.source || 'ops_state'],
      ['STAND', host.lastOps?.observed_at || 'UNKNOWN'],
    ];
    tech.textContent = rows.map(([k, v]) => `${k.padEnd(10)} ${v}`).join('\n');
  }
}
