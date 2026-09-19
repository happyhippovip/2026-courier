/* Muse workbench: 4 slots, native text editing, draft persistence,
   gallery LOAD (never auto-executes), QUEUE/RUN via file-backed queue.
   No execution backend here: RUN marks slot QUEUED; a runner claims via
   POST /api/muse/claim. All displayed states reflect server/file state. */
(function () {
  "use strict";
  var SLOTS = ["CHAT 1", "CHAT 2", "CHAT 3", "CHAT 4"];
  var VALID = ["IDLE", "QUEUED", "RUNNING", "COMPLETED", "BLOCKED", "FAILED"];
  var DEMO = new URLSearchParams(location.search).get("demo") === "1";
  if (DEMO) document.getElementById("demo-banner").style.display = "inline";

  function mask(s) {
    if (!DEMO) return s;
    return String(s)
      .replace(/\/Users\/[^ \n]*/g, "~")
      .replace(/Bearer [^ \n]*/g, "Bearer ***")
      .replace(/sk-[A-Za-z0-9_-]+/g, "***");
  }

  var state = {}; // slot -> {draft, gallery, task_id, status, source, result}
  SLOTS.forEach(function (name) {
    var saved = null;
    try { saved = JSON.parse(localStorage.getItem("muse-bench:" + name) || "null"); } catch (e) {}
    state[name] = saved || { draft: "", gallery: "", task_id: "", status: "IDLE", source: "", result: "" };
    if (VALID.indexOf(state[name].status) < 0) state[name].status = "IDLE";
  });

  function persist(name) {
    try { localStorage.setItem("muse-bench:" + name, JSON.stringify(state[name])); } catch (e) {}
  }

  var tabsEl = document.getElementById("tabs");
  var slotsEl = document.getElementById("slots");
  var els = {}; // slot -> {ta, status, source, result}
  var active = SLOTS[0];

  SLOTS.forEach(function (name) {
    var tab = document.createElement("button");
    tab.textContent = name;
    tab.onclick = function () { show(name); };
    tabsEl.appendChild(tab);

    var div = document.createElement("div");
    div.className = "slot";
    div.innerHTML =
      '<textarea class="prompt" aria-label="prompt"></textarea>' +
      '<div class="status"></div>' +
      '<div class="row">' +
      '<button class="action" data-op="run">RUN</button>' +
      '<button class="action" data-op="queue">QUEUE</button>' +
      '<span class="task"></span></div>' +
      '<h4>Source / execution</h4><pre class="view source"></pre>' +
      '<h4>Result</h4><pre class="view result"></pre>';
    slotsEl.appendChild(div);

    var ta = div.querySelector("textarea");
    ta.value = state[name].draft;
    ta.addEventListener("input", function () {
      state[name].draft = ta.value;
      persist(name);
    });
    div.querySelectorAll("button.action").forEach(function (btn) {
      btn.onclick = function () { submit(name, btn.getAttribute("data-op")); };
    });
    els[name] = { tab: tab, div: div, ta: ta,
      status: div.querySelector(".status"),
      task: div.querySelector(".task"),
      source: div.querySelector(".source"),
      result: div.querySelector(".result") };
    render(name);
  });

  function show(name) {
    active = name; // switching never clears drafts/results (persisted above)
    SLOTS.forEach(function (s) {
      var on = s === name;
      els[s].tab.classList.toggle("active", on);
      els[s].div.classList.toggle("active", on);
    });
  }

  function render(name) {
    var st = state[name];
    els[name].status.textContent = "STATUS: " + st.status;
    els[name].task.textContent = st.task_id ? ("task: " + mask(st.task_id)) : "";
    els[name].source.textContent = mask(st.source || "(no execution info)");
    els[name].result.textContent = mask(st.result || "(no result)");
  }

  function submit(name, op) {
    var prompt = els[name].ta.value;
    if (!prompt.trim()) return;
    var st = state[name];
    var body = {
      slot: name,
      template_id: st.gallery || "CUSTOM",
      template_version: st.gallery_version || "1.0.0",
      inputs: st.gallery_inputs || {},
      prompt: prompt
    };
    fetch("/api/muse/queue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); }).then(function (data) {
      if (data.ok) {
        st.task_id = data.task.task_id;
        st.status = "QUEUED"; // honest: queued until a runner claims it
        st.source = "queued at " + data.task.queued_at + " (op=" + op + ")";
        persist(name);
        render(name);
        refreshQueueInfo();
      }
    }).catch(function (err) {
      st.status = "BLOCKED";
      st.source = "queue unreachable: " + err;
      persist(name);
      render(name);
    });
  }

  function refreshQueueInfo() {
    fetch("/api/muse/state").then(function (r) { return r.json(); }).then(function (data) {
      var counts = {};
      (data.queue || []).forEach(function (t) {
        counts[t.state] = (counts[t.state] || 0) + 1;
      });
      document.getElementById("queue-info").textContent =
        "queue: " + JSON.stringify(counts) + " results: " + (data.results || []).length;
      // reflect real task states back into slots
      var changed = false;
      (data.queue || []).forEach(function (t) {
        var s = state[t.slot];
        if (s && s.task_id === t.task_id && s.status !== t.state && VALID.indexOf(t.state) >= 0) {
          s.status = t.state;
          persist(t.slot);
          changed = true;
        }
      });
      (data.results || []).forEach(function () {});
      if (changed) SLOTS.forEach(render);
    }).catch(function () {});
  }

  // Gallery: LOAD populates the ACTIVE slot editor only. Never executes.
  fetch("/api/muse/gallery").then(function (r) { return r.json(); }).then(function (g) {
    var list = document.getElementById("gallery-list");
    (g.templates || []).forEach(function (t) {
      var btn = document.createElement("button");
      btn.className = "action";
      btn.textContent = "LOAD " + t.template_id + " v" + t.version;
      btn.onclick = function () {
        var st = state[active];
        st.gallery = t.template_id;
        st.gallery_version = t.version;
        st.gallery_inputs = {};
        els[active].ta.value = "[" + t.template_id + " v" + t.version + "] " + t.objective +
          "\nInputs required: " + JSON.stringify(t.required_inputs);
        st.draft = els[active].ta.value; // LOAD = prompt only, no execution
        persist(active);
      };
      list.appendChild(btn);
    });
  }).catch(function () {});

  show(active);
  refreshQueueInfo();
  setInterval(refreshQueueInfo, 15000); // bounded state refresh, no busy poll
})();
