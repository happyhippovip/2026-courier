// Courier Desktop Hub — pure view logic (lane L5).
// No DOM access here: everything is a function of the hub API's JSON, so it is
// tested with `node --test tests/desktop`. The page (hub.js) only wires it up.

export const PILES = Object.freeze([
  { key: 'needs_you', title: 'Needs you', empty: 'Nothing needs you right now.' },
  { key: 'working', title: 'Working', empty: 'Courier is not working on anything right now.' },
  { key: 'done', title: 'Done', empty: 'Nothing has finished yet.' },
]);

// Flat marks. Only "check" means verified by Courier; a human confirmation uses
// "signature" and an uncertain stop uses "gate-question" — never the check.
export const MARKS = Object.freeze({
  check: { glyph: '✓', name: 'Checked by Courier' },
  signature: { glyph: '✍', name: 'Confirmed by a person' },
  'open-ring': { glyph: '◌', name: "Couldn't complete" },
  gate: { glyph: '▮', name: 'Stopped' },
  'gate-question': { glyph: '?', name: 'Outcome uncertain' },
  neutral: { glyph: '•', name: 'Completed' },
});

export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function timeAgo(iso, now = Date.now()) {
  const t = Date.parse(iso || '');
  if (Number.isNaN(t)) return '';
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 45) return 'just now';
  if (s < 90) return '1 minute ago';
  if (s < 3600) return `${Math.round(s / 60)} minutes ago`;
  if (s < 5400) return '1 hour ago';
  if (s < 86400) return `${Math.round(s / 3600)} hours ago`;
  return new Date(t).toISOString().slice(0, 10);
}

// ---------------------------------------------------------------- status line
export function statusLine(view, connection, now = Date.now()) {
  if (connection.state === 'offline') {
    const when = connection.lastGoodAt ? ` Last updated ${timeAgo(connection.lastGoodAt, now)}.` : '';
    return { tone: 'warn', text: `Can't reach the hub — showing the last known state.${when}` };
  }
  if (!view) return { tone: 'quiet', text: 'Loading…' };
  if (view.truth === 'not_set_up') return { tone: 'quiet', text: "Courier hasn't been set up on this computer yet." };
  if (view.truth === 'updating') return { tone: 'warn', text: 'Courier is updating its records. This view will return shortly.' };
  if (view.truth === 'unreadable') return { tone: 'warn', text: "Courier's records can't be read right now." };
  const c = view.status?.controller;
  if (c === 'safe_mode') {
    return { tone: 'warn', text: "Courier is in safe mode: you can look at everything, but it won't change anything until this is fixed." };
  }
  if (c === 'unreachable') {
    return { tone: 'warn', text: "Courier isn't running. Showing what it last recorded; decisions are paused until it's back." };
  }
  const n = view.counts || {};
  const parts = [];
  parts.push(n.needs_you ? `${n.needs_you} need${n.needs_you === 1 ? 's' : ''} you` : 'nothing needs you');
  parts.push(`${n.working || 0} working`);
  parts.push(`${n.done || 0} done`);
  const text = parts.join(' · ');
  return { tone: 'ok', text: text.charAt(0).toUpperCase() + text.slice(1) };
}

export function decisionsAllowed(view, connection) {
  return connection.state !== 'offline' && view?.status?.controller === 'running';
}

// -------------------------------------------------------------- connection
// live -> (fetch fails) -> reconnecting -> (2 more failures) -> offline -> (success) -> live
export function initialConnection() {
  return { state: 'connecting', failures: 0, lastGoodAt: null };
}

export function nextConnection(prev, event) {
  if (event.type === 'ok') return { state: 'live', failures: 0, lastGoodAt: event.at };
  const failures = prev.failures + 1;
  return { state: failures >= 3 ? 'offline' : 'reconnecting', failures, lastGoodAt: prev.lastGoodAt };
}

export function retryDelayMs(connection) {
  if (connection.state === 'live' || connection.state === 'connecting') return 3000;
  return Math.min(30000, 2000 * 2 ** Math.min(connection.failures, 4));
}

// ------------------------------------------------------------------ cards
function markHtml(mark) {
  const m = MARKS[mark] || MARKS.neutral;
  return `<span class="mark mark-${escapeHtml(mark)}" aria-hidden="true">${m.glyph}</span>`;
}

export function renderCard(card, opts = {}) {
  const now = opts.now ?? Date.now();
  const id = escapeHtml(card.id);
  const when = card.last_change ? `<span class="when">${escapeHtml(card.last_change.what)} · ${escapeHtml(timeAgo(card.last_change.at, now))}</span>` : '';
  if (card.pile === 'needs_you') {
    const n = card.needs_you;
    const allowed = opts.decisionsAllowed !== false;
    const pending = opts.pendingDecision === card.id;
    const buttons = n.choices.map((choice) => `<button type="button" class="choice choice-${escapeHtml(choice.decision)}"
        data-action="decide" data-id="${id}" data-decision="${escapeHtml(choice.decision)}" data-attempt="${escapeHtml(n.blocked_attempt)}"
        ${allowed && !pending ? '' : 'disabled aria-disabled="true"'}>${escapeHtml(choice.label)}</button>`).join('');
    const explains = n.choices.map((c) => `<li><strong>${escapeHtml(c.label)}:</strong> ${escapeHtml(c.explains)}</li>`).join('');
    const noRetry = n.retry_unavailable_reason ? `<p class="note">${escapeHtml(n.retry_unavailable_reason)}</p>` : '';
    const evidence = n.evidence.length ? `<p class="note">${escapeHtml(n.evidence.length)} late report(s) arrived — see details.</p>` : '';
    return `<article class="card card-needs" data-id="${id}" aria-labelledby="t-${id}">
  <h3 id="t-${id}" class="card-title">${escapeHtml(n.question)}</h3>
  <p class="why">${escapeHtml(n.why)}</p>
  <p class="consequence">${escapeHtml(n.consequence)}</p>
  <ul class="explains">${explains}</ul>${noRetry}${evidence}
  <div class="choices" role="group" aria-label="Your decision">${buttons}</div>
  ${pending ? '<p class="pending" role="status">Sending your decision…</p>' : ''}
  <p class="meta"><span class="item-title">${escapeHtml(card.title)}</span>${when ? ' · ' : ''}${when}
  <button type="button" class="link" data-action="details" data-id="${id}">Details</button></p>
</article>`;
  }
  if (card.pile === 'working') {
    const stopping = card.phase === 'stopping';
    return `<article class="card card-working" data-id="${id}" aria-labelledby="t-${id}">
  <h3 id="t-${id}" class="card-title"><span class="pulse" aria-hidden="true"></span>${escapeHtml(card.title)}</h3>
  <p class="phase">${escapeHtml(card.label)}</p>
  <p class="next">${escapeHtml(card.next)}</p>
  <p class="authority-line"><span class="quiet">Courier may:</span> ${escapeHtml(card.authority.may.join(' · '))}</p>
  <p class="authority-line"><span class="quiet">Must ask before:</span> ${escapeHtml(card.authority.must_ask.join(' · '))}</p>
  <p class="meta">${when}
  <button type="button" class="link" data-action="details" data-id="${id}">Details</button>
  ${stopping || !card.stop ? '' : `<button type="button" class="link danger" data-action="stop" data-id="${id}" ${opts.decisionsAllowed === false ? 'disabled aria-disabled="true"' : ''}>Stop</button>`}</p>
</article>`;
  }
  return `<article class="card card-done outcome-${escapeHtml(card.outcome)}" data-id="${id}" aria-labelledby="t-${id}">
  <h3 id="t-${id}" class="card-title">${markHtml(card.mark)}<span class="outcome-label">${escapeHtml(card.label)}</span></h3>
  <p class="item-title">${escapeHtml(card.title)}</p>
  <p class="explanation">${escapeHtml(card.explanation)}</p>
  <p class="meta">${when}
  <button type="button" class="link" data-action="details" data-id="${id}">Receipt</button></p>
</article>`;
}

export function renderHome(view, opts = {}) {
  return PILES.map((pile) => {
    const cards = (view?.[pile.key] || []);
    const count = cards.length;
    const body = count
      ? cards.map((c) => renderCard(c, opts)).join('\n')
      : `<p class="empty">${escapeHtml(pile.empty)}</p>`;
    const badge = pile.key === 'needs_you' && count ? `<span class="count" aria-label="${count} waiting">${count}</span>` : '';
    return `<section class="pile pile-${pile.key}" aria-labelledby="h-${pile.key}">
  <h2 id="h-${pile.key}">${escapeHtml(pile.title)} ${badge}</h2>
  ${body}
</section>`;
  }).join('\n');
}

// ----------------------------------------------------------------- receipt
export function renderReceipt(item, opts = {}) {
  const r = item.receipt;
  const now = opts.now ?? Date.now();
  const li = (rows, f) => rows.length ? `<ul>${rows.map(f).join('')}</ul>` : '<p class="quiet">None.</p>';
  const authority = `<div class="authority"><h4>Courier may, without asking again</h4>${li(r.authorized.may, (x) => `<li>${escapeHtml(x)}</li>`)}
<h4>Courier must ask before</h4>${li(r.authorized.must_ask, (x) => `<li>${escapeHtml(x)}</li>`)}
<p class="note">${escapeHtml(r.authorized.note)}</p></div>`;
  const steps = li(r.tried, (s) => `<li>${escapeHtml(s.what)} <span class="when">${escapeHtml(timeAgo(s.at, now))}</span></li>`);
  const decisions = li(r.decisions, (d) => `<li><strong>${escapeHtml(d.who)}</strong> — ${escapeHtml(d.decided)}${d.reason ? `: “${escapeHtml(d.reason)}”` : ''} <span class="when">${escapeHtml(timeAgo(d.at, now))}</span></li>`);
  const later = li(r.changed_later, (s) => `<li>${escapeHtml(s.what)} <span class="when">${escapeHtml(timeAgo(s.at, now))}</span></li>`);
  const evidence = li(r.evidence, (e) => `<li>${escapeHtml(e.name)}${e.accepted ? ' — checked' : ''}</li>`);
  const support = escapeHtml(JSON.stringify(item.support, null, 2));
  return `<h2 class="receipt-title">${escapeHtml(item.card.title)}</h2>
<dl class="receipt">
  <dt>What Courier understood</dt><dd>${escapeHtml(r.understood)}</dd>
  <dt>What Courier was allowed to do</dt><dd>${authority}</dd>
  <dt>What Courier did</dt><dd>${steps}${r.resumed ? '<p class="note">Courier resumed after an interruption.</p>' : ''}</dd>
  <dt>What happened</dt><dd>${escapeHtml(r.happened)}</dd>
  <dt>How Courier knows</dt><dd>${escapeHtml(r.how_known)}</dd>
  <dt>Who decided</dt><dd>${decisions}</dd>
  <dt>What changed later</dt><dd>${later}</dd>
  <dt>Evidence</dt><dd>${evidence}</dd>
</dl>
<details class="support"><summary>For support</summary><pre>${support}</pre>
<p><a href="/hub/api/items/${encodeURIComponent(item.card.id)}/support" download>Save support record</a> — this item only; no passwords or keys.</p></details>`;
}

// ---------------------------------------------------------------- decisions
// One decision per item at a time: a second click while one is in flight
// returns the same promise instead of sending a second request.
export function createDecisionClient(fetchFn) {
  const inFlight = new Map();
  async function post(path, body) {
    let response;
    try {
      response = await fetchFn(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Courier-Hub': '1' },
        body: JSON.stringify(body),
      });
    } catch {
      // The request may have left the browser before the connection broke: the
      // decision may or may not be recorded. Never claim that nothing changed.
      return interpretResponse(-1, null);
    }
    let payload = null;
    try { payload = await response.json(); } catch { payload = null; }
    return interpretResponse(response.status, payload);
  }
  function once(key, run) {
    if (inFlight.has(key)) return inFlight.get(key);
    const p = run().finally(() => inFlight.delete(key));
    inFlight.set(key, p);
    return p;
  }
  return {
    decide(id, decision, attempt, note) {
      return once(id, () => post(`/hub/api/items/${encodeURIComponent(id)}/decision`, { decision, attempt, note }));
    },
    stop(id) {
      return once(id, () => post(`/hub/api/items/${encodeURIComponent(id)}/stop`, {}));
    },
    busy(id) { return inFlight.has(id); },
  };
}

export function interpretResponse(status, payload) {
  if (status === -1 || status === 0) {
    return { kind: 'unknown', message: "Couldn't confirm whether your decision arrived. Courier keeps the record: the list refreshes with what it has recorded." };
  }
  const result = payload?.result;
  if (status === 200 && result === 'recorded') return { kind: 'success', message: 'Recorded.', item: payload.item };
  if (status === 200 && result === 'already_recorded') {
    return { kind: 'already', message: 'This decision was already recorded.', item: payload.item };
  }
  if (result === 'stale') return { kind: 'stale', message: payload.message, item: payload.item };
  if (result === 'unknown') return { kind: 'unknown', message: payload.message, item: payload.item };
  if (result === 'offline' || result === 'unavailable') return { kind: 'offline', message: payload.message };
  if (status >= 500 || status === 200 || !payload?.message) {
    // No answer the hub vouches for: the decision may have been recorded.
    return interpretResponse(-1, null);
  }
  return { kind: 'error', message: payload.message };
}

// A stable fingerprint of what Home would show; the page re-renders only when it
// changes (or once a minute for relative times), so an idle hub stays quiet.
export function viewSignature(view, connection, pending) {
  return JSON.stringify([view?.head_seq, view?.truth, view?.status?.controller, connection.state, pending,
    view?.counts]);
}

export function findChoice(view, id, decision) {
  const card = (view?.needs_you || []).find((c) => c.id === id);
  return card ? card.needs_you.choices.find((c) => c.decision === decision) || null : null;
}

export function renderWorkspaceStrip(view, opts = {}) {
  const summary = view?.summary;
  if (!summary) return '';
  const watermark = opts.watermark;
  const now = opts.now ?? Date.now();
  const items = PILES.map((pile) => {
    const s = summary[pile.key] || { count: 0, latest_change: null };
    const when = s.latest_change ? timeAgo(s.latest_change, now) : 'no activity';
    const isNew = Boolean(watermark && s.latest_change && s.latest_change > watermark);
    const badge = isNew ? ' <span class="strip-marker">Updated</span>' : '';
    return `<div class="strip-item strip-${pile.key}">` +
      `<span class="strip-label">${escapeHtml(pile.title)}</span>: ` +
      `<span class="strip-count">${s.count}</span> ` +
      `<span class="strip-when">(${escapeHtml(when)})</span>` +
      `${badge}</div>`;
  }).join('');
  return `<div class="workspace-strip-inner">${items}</div>`;
}
