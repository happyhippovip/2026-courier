import {WorkScript} from './controller.mjs';
import {WORK_PROMPT} from './prompt.mjs';

export function mountWorkScript(host, adapter = null) {
  const root = host.attachShadow({mode: 'open'});
  root.innerHTML = `<style>
    :host{display:block;font:16px system-ui;color:#e5edf9}
    section{background:#101e2b;border:1px solid #344559;border-radius:18px;padding:24px;max-width:600px}
    button{border:1px solid #56708c;border-radius:12px;background:#263547;color:white;padding:16px 26px;font-weight:800;font-size:18px;cursor:pointer}
    button[aria-pressed=true]{background:#05733e;border-color:#57f0a0;animation:pulse 2s ease-in-out infinite}
    @keyframes pulse{50%{box-shadow:0 0 18px #34eb81}}
    @media(prefers-reduced-motion:reduce){button[aria-pressed=true]{animation:none}}
    p{line-height:1.5}small{color:#a9bdcf}details{margin-top:20px}pre{white-space:pre-wrap;font:14px system-ui}
    [role=status]{color:#ffd682;font-weight:600}
  </style><section>
    <button type="button" aria-pressed="false">WORK SCRIPT</button>
    <p role="status" aria-live="polite">AUS</p>
    <p>Prüfung alle 2 Minuten. Grün bedeutet eingeschaltet. Der Lichtpuls alle 2 Sekunden sendet nichts.</p>
    <small>Nur eine bestätigte freie Muse-Sitzung erhält neue autorisierte Arbeit. Ausschalten stoppt neue Sendungen; bereits angenommene Arbeit läuft weiter.</small>
    <details><summary>Gesendeter Arbeitsauftrag</summary><pre></pre></details>
    <p><small data-receipt>Noch keine bestätigte Übergabe.</small></p>
  </section>`;
  root.querySelector('pre').textContent = WORK_PROMPT;
  const messages = {
    OFF:'AUS', ARMED:'AN · nächste Prüfung in 2 Minuten', NOT_CONNECTED:'NICHT VERBUNDEN · Muse-CLI-Anbindung fehlt',
    BLOCKED_CONFIGURATION:'BLOCKIERT · Speicher oder Browser-Sperre fehlt', BUSY:'AN · Muse arbeitet bereits',
    BUSY_OTHER_TAB:'AN · anderer Tab prüft gerade', IDLE:'PAUSIERT · keine freigegebene Arbeit',
    UNCHANGED:'AN · unveränderter Auftrag wird nicht erneut gesendet', SUBMITTING:'AN · Übergabe läuft',
    SENT:'AN · Übergabe bestätigt; Ausführung noch nicht bewiesen', BLOCKED_AUTHORITY:'BLOCKIERT · Freigabe oder Zielzustand fehlt',
    BLOCKED_PROTOCOL:'BLOCKIERT · ungültige Anbindung', BLOCKED_REJECTED:'BLOCKIERT · Übergabe abgelehnt',
    BLOCKED_UNCONFIRMED:'BLOCKIERT · alte Übergabe muss geprüft werden',
    BLOCKED_CHECK_OR_DELIVERY:'BLOCKIERT · Prüfung oder Übergabe unbestätigt',
    BLOCKED_JOURNAL_FULL:'BLOCKIERT · Übergabejournal voll'
  };
  let storage = null;
  try {storage = window.localStorage;} catch {}
  const controller = new WorkScript({adapter, storage, prompt: WORK_PROMPT,
    lock: navigator.locks ? fn => navigator.locks.request('courier.work-script.v1',
      {ifAvailable:true}, lease => fn(Boolean(lease))) : null,
    onChange: state => {
      root.querySelector('button').setAttribute('aria-pressed', String(state.enabled));
      root.querySelector('[role=status]').textContent = messages[state.status] || 'BLOCKIERT';
      if (state.lastReceipt) root.querySelector('[data-receipt]').textContent =
        'Letzte bestätigte Übergabe: ' + new Date(state.lastReceipt).toLocaleTimeString();
    }
  });
  root.querySelector('button').onclick = () => controller.enabled ? controller.stop() : controller.start();
  const stop = () => controller.stop();
  window.addEventListener('pagehide', stop);
  return {controller, destroy(){stop();window.removeEventListener('pagehide', stop);root.innerHTML='';}};
}
