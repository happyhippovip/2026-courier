// Courier Desktop Hub — page wiring (lane L5). All decisions about what to show
// live in hub_core.mjs; this file only fetches, renders and handles input.
import {
  createDecisionClient, decisionsAllowed, findChoice, initialConnection, nextConnection,
  renderHome, renderReceipt, retryDelayMs, statusLine, viewSignature,
} from './hub_core.mjs';

const $ = (sel) => document.querySelector(sel);
const state = { view: null, connection: initialConnection(), pending: null, openItem: null, timer: null,
  rendered: null, renderedAt: 0 };
const client = createDecisionClient((url, init) => fetch(url, init));

function announce(text, tone = 'ok') {
  const box = $('#toast');
  box.textContent = text;
  box.dataset.tone = tone;
  box.hidden = !text;
}

function render({ force = false } = {}) {
  const signature = viewSignature(state.view, state.connection, state.pending);
  if (!force && signature === state.rendered && Date.now() - state.renderedAt < 60000) return;  // nothing changed
  state.rendered = signature;
  state.renderedAt = Date.now();
  const line = statusLine(state.view, state.connection);
  const status = $('#status');
  status.textContent = line.text;
  status.dataset.tone = line.tone;
  if (state.view) {
    const focusedId = document.activeElement?.dataset?.id;
    const focusedAction = document.activeElement?.dataset?.action;
    $('#piles').innerHTML = renderHome(state.view, {
      decisionsAllowed: decisionsAllowed(state.view, state.connection),
      pendingDecision: state.pending,
    });
    if (focusedId) {  // keep keyboard focus across refreshes
      const again = document.querySelector(`[data-id="${CSS.escape(focusedId)}"][data-action="${focusedAction}"]`);
      again?.focus();
    }
  }
}

async function refresh() {
  clearTimeout(state.timer);
  try {
    const response = await fetch('/hub/api/home', { cache: 'no-store' });
    if (!response.ok) throw new Error(String(response.status));
    state.view = await response.json();
    state.connection = nextConnection(state.connection, { type: 'ok', at: new Date().toISOString() });
  } catch {
    state.connection = nextConnection(state.connection, { type: 'fail' });
  }
  render();
  if (state.openItem && state.view && state.view.head_seq !== state.openItemSeq) {
    state.openItemSeq = state.view.head_seq;  // reload the receipt only when the record changed
    await loadItem(state.openItem, { quiet: true });
  }
  state.timer = document.hidden ? null : setTimeout(refresh, retryDelayMs(state.connection));
}

async function loadItem(id, { quiet = false } = {}) {
  try {
    const response = await fetch(`/hub/api/items/${encodeURIComponent(id)}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(String(response.status));
    $('#detail-body').innerHTML = renderReceipt(await response.json());
  } catch {
    if (!quiet) $('#detail-body').textContent = "Couldn't load this item. It will reappear when the hub is reachable.";
  }
}

function openDetail(id) {
  state.openItem = id;
  state.openItemSeq = state.view?.head_seq;
  const panel = $('#detail');
  panel.hidden = false;
  $('#detail-body').textContent = 'Loading…';
  loadItem(id);
  $('#detail-close').focus();
}

function closeDetail() {
  const id = state.openItem;
  state.openItem = null;
  $('#detail').hidden = true;
  document.querySelector(`[data-id="${CSS.escape(id || '')}"][data-action="details"]`)?.focus();
}

function confirmChoice(choice) {
  // Only "Try once more" carries a consequence warning; it is shown before anything is sent.
  if (!choice?.confirm) return Promise.resolve(true);
  const dialog = $('#confirm');
  $('#confirm-text').textContent = choice.confirm;
  dialog.showModal();
  return new Promise((resolve) => {
    dialog.addEventListener('close', () => resolve(dialog.returnValue === 'yes'), { once: true });
  });
}

async function decide(button) {
  const { id, decision, attempt } = button.dataset;
  if (client.busy(id)) return;  // duplicate click: one decision in flight per item
  const choice = findChoice(state.view, id, decision);
  if (!(await confirmChoice(choice))) return;
  state.pending = id;
  render({ force: true });
  const result = await client.decide(id, decision, Number(attempt));
  state.pending = null;
  announce(result.message, result.kind === 'success' || result.kind === 'already' ? 'ok' : 'warn');
  await refresh();
  render({ force: true });
}

async function stop(button) {
  const { id } = button.dataset;
  if (client.busy(id)) return;
  const result = await client.stop(id);
  announce(result.kind === 'success' ? 'Stop requested. Courier stops at the next safe point.' : result.message,
    result.kind === 'success' ? 'ok' : 'warn');
  await refresh();
}

document.addEventListener('click', (event) => {
  const button = event.target.closest('button[data-action]');
  if (!button || button.disabled) return;
  if (button.dataset.action === 'decide') decide(button);
  else if (button.dataset.action === 'details') openDetail(button.dataset.id);
  else if (button.dataset.action === 'stop') stop(button);
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !$('#detail').hidden && !$('#confirm').open) closeDetail();
  if (event.key === 'r' && !event.ctrlKey && !event.metaKey && document.activeElement?.tagName !== 'TEXTAREA') refresh();
});

$('#detail-close').addEventListener('click', closeDetail);
$('#refresh').addEventListener('click', () => refresh());
window.addEventListener('focus', () => refresh());
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
window.addEventListener('online', () => refresh());
refresh();
