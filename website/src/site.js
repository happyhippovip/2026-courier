(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var fine = window.matchMedia("(pointer: fine)").matches;

  function pulse(kind) {
    document.dispatchEvent(new CustomEvent("courier:pulse", { detail: { kind: kind } }));
  }

  function $(id) { return document.getElementById(id); }

  document.querySelectorAll("#site-nav a, .quick a").forEach(function (link) {
    link.addEventListener("click", function () {
      var box = $("nav-check");
      if (box) box.checked = false;
      pulse("bridge");
    });
  });

  var skyBtn = $("sky-toggle");
  if (skyBtn) {
    skyBtn.addEventListener("click", function () {
      var day = document.body.getAttribute("data-sky") === "day";
      document.body.setAttribute("data-sky", day ? "night" : "day");
      skyBtn.setAttribute("aria-pressed", day ? "false" : "true");
      skyBtn.textContent = day ? "Tag" : "Nacht";
    });
  }

  var hero = document.querySelector(".hero");
  if (hero && "IntersectionObserver" in window) {
    var watch = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        hero.classList.toggle("is-offscreen", !entry.isIntersecting);
      });
    }, { threshold: 0 });
    watch.observe(hero);
  }

  if (hero && fine && !reduced) {
    var city = hero.querySelector(".city");
    var ticking = false;
    window.addEventListener("scroll", function () {
      if (ticking || hero.classList.contains("is-offscreen")) return;
      ticking = true;
      window.requestAnimationFrame(function () {
        var y = Math.max(-16, Math.min(16, window.scrollY * 0.04));
        if (city) city.style.transform = "translateY(" + y + "px)";
        ticking = false;
      });
    }, { passive: true });
  }

  document.addEventListener("courier:pulse", function (event) {
    var kind = event.detail && event.detail.kind;
    if (kind === "bridge") {
      document.body.classList.add("bridge-lit");
      window.setTimeout(function () { document.body.classList.remove("bridge-lit"); }, 900);
    }
    if (kind === "portal") {
      var ring = document.querySelector(".portal-ring");
      if (ring) ring.classList.add("bridge-lit");
    }
    if (kind === "stars") {
      var box = $("stars");
      if (!box || reduced) return;
      box.textContent = "";
      for (var i = 0; i < 5; i += 1) {
        var star = document.createElement("span");
        star.textContent = "✦";
        box.appendChild(star);
      }
    }
  });

  function places() { return Array.prototype.slice.call(document.querySelectorAll("article.place")); }
  function stars() { return Array.prototype.slice.call(document.querySelectorAll("a.star")); }

  function currentFilters() {
    function val(id) {
      var el = $(id);
      return el ? el.value : "";
    }
    var catBtn = document.querySelector("#cat-filters [aria-pressed='true']");
    return {
      cat: catBtn ? catBtn.getAttribute("data-cat") : "",
      skill: val("f-skill"),
      interest: val("f-interest"),
      topic: val("f-topic"),
      lang: val("f-lang"),
      when: val("f-when"),
      size: val("f-size")
    };
  }

  function match(el, filters) {
    function has(attr, value) {
      if (!value) return true;
      return (el.getAttribute(attr) || "").toLowerCase().indexOf(value.toLowerCase()) !== -1;
    }
    if (filters.cat && el.getAttribute("data-cat") !== filters.cat) return false;
    if (!has("data-skills", filters.skill)) return false;
    if (!has("data-interests", filters.interest)) return false;
    if (!has("data-topic", filters.topic)) return false;
    if (filters.lang && el.getAttribute("data-lang") !== filters.lang) return false;
    if (filters.when && el.getAttribute("data-when") !== filters.when) return false;
    if (filters.size && el.getAttribute("data-size") !== filters.size) return false;
    return true;
  }

  function applyFilters() {
    var filters = currentFilters();
    var shown = 0;
    places().forEach(function (el) {
      var ok = match(el, filters);
      el.hidden = !ok;
      if (ok) shown += 1;
    });
    stars().forEach(function (el) {
      var id = (el.getAttribute("href") || "").slice(1);
      var card = id ? $(id) : null;
      el.hidden = !(card && !card.hidden);
    });
    var empty = $("filter-empty");
    if (empty) empty.hidden = shown !== 0;
  }

  document.querySelectorAll("#cat-filters button").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll("#cat-filters button").forEach(function (other) {
        other.setAttribute("aria-pressed", other === btn ? "true" : "false");
      });
      applyFilters();
    });
  });
  ["f-skill", "f-interest", "f-topic", "f-lang", "f-when", "f-size"].forEach(function (id) {
    var el = $(id);
    if (el) el.addEventListener("change", applyFilters);
  });

  var instant = $("instant");
  if (instant) {
    instant.addEventListener("submit", function (event) {
      event.preventDefault();
      var picked = Array.prototype.map.call(instant.querySelectorAll("input:checked"), function (box) {
        return box.value;
      });
      var shown = 0;
      places().forEach(function (el) {
        var interests = el.getAttribute("data-interests") || "";
        var ok = picked.length === 0 || picked.some(function (token) { return interests.indexOf(token) !== -1; });
        el.hidden = !ok;
        if (ok) shown += 1;
      });
      stars().forEach(function (el) {
        var card = $((el.getAttribute("href") || "").slice(1));
        el.hidden = !(card && !card.hidden);
      });
      var empty = $("instant-empty");
      if (empty) empty.hidden = shown !== 0;
      pulse("bridge");
    });
  }

  document.querySelectorAll(".join").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var note = btn.parentElement.querySelector(".join-result");
      if (!note) return;
      note.hidden = false;
      if (btn.getAttribute("data-voice") === "soon") {
        note.textContent = "Voice · Bald verfügbar. Es wird kein Raum geöffnet und niemand angerufen.";
      } else {
        note.textContent = "Demo. Es wird niemand hinzugefügt und kein Konto angelegt.";
      }
      pulse("bridge");
    });
  });

  document.querySelectorAll("[data-emote]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll("[data-emote]").forEach(function (other) {
        other.setAttribute("aria-pressed", other === btn ? "true" : "false");
      });
      var out = $("emote-out");
      if (out) out.textContent = "Dein Zeichen: " + btn.getAttribute("data-emote") + ". Wird nicht gesendet. Niemand sonst sieht es.";
    });
  });

  document.querySelectorAll("[data-prompt]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var out = $("prompt-out");
      if (out) out.textContent = btn.getAttribute("data-prompt");
    });
  });

  var layouts = {
    fenster: "Fenstertisch. Drei leere Stühle am Glas. Illustrativ. Niemand sitzt hier.",
    bruecke: "Brückentisch. Zwei leere Plätze über dem Licht. Illustrativ. Niemand sitzt hier.",
    kamin: "Kamin. Ein leerer Kreis. Was du notierst, bleibt in diesem Fenster und wird nicht gesendet."
  };
  document.querySelectorAll("[data-table]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll("[data-table]").forEach(function (other) {
        other.setAttribute("aria-pressed", other === btn ? "true" : "false");
      });
      document.querySelectorAll(".seat").forEach(function (seat) {
        seat.classList.toggle("lit", seat.getAttribute("data-seat") === btn.getAttribute("data-table"));
      });
      var out = $("table-out");
      if (out) out.textContent = layouts[btn.getAttribute("data-table")] || "";
    });
  });

  var fire = $("fire-form");
  if (fire) {
    fire.addEventListener("submit", function (event) {
      event.preventDefault();
      var text = (new FormData(fire).get("note") || "").toString().trim();
      var out = $("fire-note");
      if (!out) return;
      out.hidden = false;
      out.textContent = text
        ? "Nur in diesem Fenster: " + text + " Nichts wurde gesendet oder gespeichert."
        : "Der Rand bleibt leer. Nichts wurde gesendet.";
    });
  }

  document.querySelectorAll("[data-door]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var out = $("portal-result");
      if (!out) return;
      var kind = btn.getAttribute("data-door");
      var text = {
        concept: "Konzept: der Cyanarchiv-Hof, ein illustrativer Lesesaal. Keine Mitgliedschaft.",
        challenge: "Kleine Aufgabe: benenne eine Brücke und setze ein Licht. Du kannst sie unten in ein paar Schritten beenden.",
        hidden: "Versteck: der Hof hinter dem Wasserfall. Dieselbe Notiz wie beim Vogel. Illustrativ."
      }[kind];
      out.textContent = text || "";
      pulse("portal");
    });
  });

  var quest = { light: "", name: "", star: "" };
  function questReady() {
    var go = $("quest-finish");
    if (go) go.disabled = !(quest.light && quest.name && quest.star);
  }
  document.querySelectorAll("[data-light]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      quest.light = btn.getAttribute("data-light");
      document.querySelectorAll("[data-light]").forEach(function (other) {
        other.setAttribute("aria-pressed", other === btn ? "true" : "false");
      });
      questReady();
    });
  });
  document.querySelectorAll("[data-starpos]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      quest.star = btn.getAttribute("data-starpos");
      document.querySelectorAll("[data-starpos]").forEach(function (other) {
        other.setAttribute("aria-pressed", other === btn ? "true" : "false");
      });
      questReady();
    });
  });
  var nameInput = $("bridge-name");
  if (nameInput) {
    nameInput.addEventListener("input", function () {
      quest.name = nameInput.value.trim();
      questReady();
    });
  }
  var finish = $("quest-finish");
  if (finish) {
    finish.addEventListener("click", function () {
      if (finish.disabled) return;
      var done = $("quest-done");
      if (done) {
        done.hidden = false;
        done.textContent = "Geschafft. Die Brücke „" + quest.name + "“ trägt ein " + quest.light + " Licht und einen Stern " + quest.star + ". Nur in diesem Fenster.";
      }
      var bird = $("bird-status");
      if (bird) bird.textContent = "Der Vogel feiert die beendete Demo und setzt sich wieder.";
      pulse("stars");
      document.dispatchEvent(new CustomEvent("courier-demo-complete"));
    });
  }

  var secretClicks = 0;
  var bird = $("bird");
  if (bird) {
    bird.classList.add("bird-land");
    bird.addEventListener("click", function () {
      secretClicks += 1;
      var secret = $("secret");
      var status = $("bird-status");
      if (secret) secret.hidden = false;
      if (secretClicks === 1 && status) status.textContent = "Der Vogel hat das Versteck bemerkt.";
      if (secretClicks === 2 && status) status.textContent = "Zweiter Blick: dasselbe Versteck, kein zweites Konto.";
      if (secretClicks >= 3) {
        bird.classList.add("bird-sleep");
        if (status) status.textContent = "Der Vogel döst. Die Seite bleibt bedienbar.";
      }
      pulse("portal");
    });
  }
  var tip = $("bird-tip");
  if (tip) {
    tip.addEventListener("click", function () {
      var node = $("tip");
      if (node) node.hidden = false;
    });
  }
  window.setTimeout(function () {
    var status = $("bird-status");
    var button = $("bird");
    if (!button || secretClicks > 0) return;
    button.classList.add("bird-sleep");
    if (status && status.textContent.indexOf("feiert") === -1) {
      status.textContent = "Der Vogel döst, bis du ihn antippst.";
    }
  }, 20000);

  var portalSection = $("portal");
  if (portalSection && "IntersectionObserver" in window) {
    var seen = false;
    var eye = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting || seen) return;
        seen = true;
        var status = $("bird-status");
        if (status && secretClicks === 0) status.textContent = "Der Vogel hat das Portal bemerkt.";
      });
    }, { threshold: 0.4 });
    eye.observe(portalSection);
  }

  var guild = $("guild-open");
  if (guild) {
    guild.addEventListener("click", function () {
      var panel = $("guild-panel");
      var open = guild.getAttribute("aria-expanded") === "true";
      guild.setAttribute("aria-expanded", open ? "false" : "true");
      if (panel) panel.hidden = open;
    });
  }

  function drawCard(place, line, filename) {
    var canvas = $("postcard");
    if (!canvas || !canvas.getContext) return "";
    canvas.hidden = false;
    var ctx = canvas.getContext("2d");
    canvas.width = 880;
    canvas.height = 520;
    ctx.fillStyle = "#10182a";
    ctx.fillRect(0, 0, 880, 520);
    ctx.strokeStyle = "#e4c27a";
    ctx.lineWidth = 6;
    ctx.strokeRect(24, 24, 832, 472);
    ctx.strokeStyle = "#7ef0ff";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.ellipse(160, 150, 70, 36, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.ellipse(250, 150, 70, 36, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.fillStyle = "#f4efe4";
    ctx.font = "42px Georgia";
    ctx.fillText("Courier Symphony", 80, 250);
    ctx.font = "28px Georgia";
    ctx.fillStyle = "#e4c27a";
    ctx.fillText(String(place).slice(0, 42), 80, 320);
    ctx.fillStyle = "#d5dbe6";
    ctx.font = "22px Georgia";
    ctx.fillText(String(line).slice(0, 90), 80, 380);
    ctx.font = "16px Georgia";
    ctx.fillText("DEMO. Kein Agentenlauf. Keine Zählung.", 80, 450);
    var url = canvas.toDataURL("image/png");
    var link = $("postcard-link");
    if (link) {
      link.hidden = false;
      link.href = url;
      link.download = filename || "courier-postkarte.png";
    }
    return url;
  }

  var card = $("postcard-form");
  if (card) {
    card.addEventListener("submit", function (event) {
      event.preventDefault();
      var place = (new FormData(card).get("place") || "Hof").toString();
      var line = (new FormData(card).get("line") || "").toString();
      drawCard(place, line, "courier-postkarte.png");
    });
  }

  var star = $("dim-star");
  if (star) {
    star.addEventListener("click", function () {
      var room = $("sternkammer");
      if (room) {
        room.hidden = false;
        room.scrollIntoView({ block: "nearest" });
      }
      var status = $("bird-status");
      if (status) status.textContent = "Der Vogel neigt den Kopf. Er hat den Stern gesehen.";
      var birdBtn = $("bird");
      if (birdBtn) birdBtn.classList.remove("bird-sleep");
    });
  }

  var replies = [
    "Ich lege den Satz an den Rand der Nachtbrücke. Am Morgen ist er noch da.",
    "Das Licht auf der Brücke merkt sich den Wunsch, nicht den Absender.",
    "Ein kleiner Hof bleibt offen, bis du wieder hinsiehst."
  ];
  var sealedWish = "";
  var wishForm = $("wish-form");
  if (wishForm) {
    wishForm.addEventListener("submit", function (event) {
      event.preventDefault();
      sealedWish = (new FormData(wishForm).get("wish") || "").toString().trim();
      if (!sealedWish) return;
      var sealed = $("sealed");
      var opened = $("opened");
      if (sealed) sealed.hidden = false;
      if (opened) opened.hidden = true;
      var status = $("bird-status");
      if (status) status.textContent = "Der Vogel hält den Umschlag. Er wartet, bis du ihn öffnest.";
    });
  }
  var opener = $("open-envelope");
  if (opener) {
    opener.addEventListener("click", function () {
      var opened = $("opened");
      if (opened) opened.hidden = false;
      var sum = 0;
      for (var i = 0; i < sealedWish.length; i += 1) sum += sealedWish.charCodeAt(i);
      var reply = replies[sum % replies.length];
      var wishLine = $("wish-line");
      var replyLine = $("reply-line");
      var result = $("receipt-result");
      if (wishLine) wishLine.textContent = "Dein Wunsch: " + sealedWish;
      if (replyLine) replyLine.textContent = reply;
      if (result) result.textContent = "Umschlag geschlossen und geöffnet. Demo.";
      var status = $("bird-status");
      if (status) status.textContent = "Der Vogel lässt den Umschlag los.";
    });
  }
  var keep = $("keep-card");
  if (keep) {
    keep.addEventListener("click", function () {
      var reply = ($("reply-line") && $("reply-line").textContent) || "";
      var url = drawCard("Morgenumschlag", sealedWish + " — " + reply, "courier-morgen.png");
      var link = $("envelope-card");
      if (link && url) {
        link.hidden = false;
        link.href = url;
      }
    });
  }
  var pay = $("pay-later");
  if (pay) {
    pay.addEventListener("click", function () {
      var note = $("pay-note");
      if (note) note.hidden = false;
    });
  }

  var roomId = null;
  var roomCursor = 0;
  var roomYou = null;
  var roomPeople = [];
  var roomStop = false;
  var roomFigure = "gold";
  var spotIndex = 0;
  var bubbles = {};

  function loungeApi(path, body) {
    return fetch(path, {
      method: body ? "POST" : "GET",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined
    }).then(function (response) {
      if (!response.ok) throw new Error(String(response.status));
      return response.json();
    });
  }

  function findAvatar(box, id) {
    var nodes = box.children;
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i].getAttribute("data-pid") === id) return nodes[i];
    }
    return null;
  }

  function paintPeople(people) {
    var box = $("lounge-people");
    if (!box) return;
    var seen = {};
    (people || []).forEach(function (person) {
      seen[person.id] = true;
      var el = findAvatar(box, person.id);
      if (!el) {
        el = document.createElement("div");
        el.className = "avatar";
        el.setAttribute("data-pid", person.id);
        var bubble = document.createElement("p");
        bubble.className = "bubble";
        bubble.hidden = true;
        var fig = document.createElement("span");
        fig.className = "fig";
        fig.setAttribute("aria-hidden", "true");
        var who = document.createElement("span");
        who.className = "who";
        el.appendChild(bubble);
        el.appendChild(fig);
        el.appendChild(who);
        box.appendChild(el);
      }
      el.style.left = person.x + "%";
      el.style.top = person.y + "%";
      el.style.zIndex = String(10 + Math.round(Number(person.y) || 0));
      el.querySelector(".fig").className = "fig fig-" + (person.figure || "gold");
      el.querySelector(".who").textContent = roomYou && person.id === roomYou.id ? "Du" : person.name;
      var bubbleEl = el.querySelector(".bubble");
      if (person.bubble) {
        bubbleEl.hidden = false;
        bubbleEl.textContent = person.bubble;
      } else {
        bubbleEl.hidden = true;
        bubbleEl.textContent = "";
      }
    });
    Array.prototype.slice.call(box.children).forEach(function (el) {
      if (!seen[el.getAttribute("data-pid")]) el.remove();
    });
  }

  function setRelay(text) {
    var relay = $("lounge-relay");
    if (relay) relay.textContent = text;
  }

  function applyRoom(data) {
    if (!data) return;
    roomCursor = data.cursor || roomCursor;
    (data.events || []).forEach(function (event) {
      if (event.kind === "line" && event.id) bubbles[event.id] = event.text || "";
      if (event.kind === "leave" && event.id) delete bubbles[event.id];
    });
    if (data.you) {
      roomYou = data.you;
      roomYou.figure = roomYou.figure || roomFigure;
      roomYou.bubble = roomYou.bubble || bubbles[roomYou.id] || "";
    }
    roomPeople = (data.people || []).map(function (person) {
      person.figure = person.figure || "gold";
      person.bubble = person.bubble || bubbles[person.id] || "";
      return person;
    });
    paintPeople(roomPeople);
    var count = roomPeople.length;
    setRelay(count > 1
      ? "Relay an. " + count + " Fenster teilen diesen Raum."
      : "Relay an. Sonst ist niemand in diesem Raum.");
  }

  function alone() {
    roomStop = true;
    roomId = null;
    if (roomYou) {
      roomPeople = [roomYou];
      paintPeople(roomPeople);
    }
    setRelay("Nur dieses Fenster. Niemand sonst ist hier.");
  }

  function pollRoom() {
    if (!roomId || roomStop) return;
    loungeApi("/api/lounge/events?id=" + encodeURIComponent(roomId) + "&since=" + roomCursor)
      .then(function (data) {
        applyRoom(data);
        pollRoom();
      })
      .catch(alone);
  }

  function walkTo(x, y) {
    if (!roomYou) return;
    roomYou.x = x;
    roomYou.y = y;
    roomPeople.forEach(function (person) {
      if (person.id === roomYou.id) {
        person.x = x;
        person.y = y;
      }
    });
    paintPeople(roomPeople);
    if (roomId) loungeApi("/api/lounge/move", { id: roomId, x: x, y: y }).catch(function () {});
  }

  function hallSpots() {
    return Array.prototype.slice.call(document.querySelectorAll("#lounge-floor .spot"));
  }

  function goSpot(index) {
    var list = hallSpots();
    if (!list.length || !roomYou) return;
    spotIndex = (index + list.length) % list.length;
    var spot = list[spotIndex];
    list.forEach(function (el, i) {
      el.setAttribute("aria-pressed", i === spotIndex ? "true" : "false");
    });
    walkTo(Number(spot.getAttribute("data-x")), Number(spot.getAttribute("data-y")));
  }

  document.querySelectorAll(".figure-pick").forEach(function (btn) {
    btn.addEventListener("click", function () {
      roomFigure = btn.getAttribute("data-figure") || "gold";
      document.querySelectorAll(".figure-pick").forEach(function (other) {
        other.setAttribute("aria-pressed", other === btn ? "true" : "false");
      });
    });
  });

  var joinForm = $("lounge-join");
  if (joinForm) {
    joinForm.addEventListener("submit", function (event) {
      event.preventDefault();
      var name = ($("lounge-name") && $("lounge-name").value || "").trim();
      if (!name) return;
      roomYou = { id: "self", name: name, x: 16, y: 58, figure: roomFigure, bubble: "" };
      roomPeople = [roomYou];
      roomStop = false;
      joinForm.hidden = true;
      var room = $("lounge-room");
      if (room) room.hidden = false;
      paintPeople(roomPeople);
      setRelay("Nur dieses Fenster. Niemand sonst ist hier.");
      var floor = $("lounge-floor");
      if (floor) floor.focus();
      loungeApi("/api/lounge/join", { name: name, figure: roomFigure }).then(function (data) {
        var x = roomYou.x;
        var y = roomYou.y;
        var bubble = roomYou.bubble;
        roomId = data.id;
        roomCursor = data.cursor || 0;
        roomStop = false;
        applyRoom(data);
        if (roomYou && (roomYou.x !== x || roomYou.y !== y)) {
          loungeApi("/api/lounge/move", { id: roomId, x: x, y: y }).catch(function () {});
        }
        if (bubble) loungeApi("/api/lounge/line", { id: roomId, text: bubble }).catch(function () {});
        pollRoom();
      }).catch(alone);
    });
  }

  hallSpots().forEach(function (spot, index) {
    spot.addEventListener("click", function () { goSpot(index); });
  });

  var sayForm = $("lounge-say");
  if (sayForm) {
    sayForm.addEventListener("submit", function (event) {
      event.preventDefault();
      var input = $("lounge-line");
      var text = input ? input.value.trim() : "";
      if (!text || !roomYou) return;
      input.value = "";
      roomYou.bubble = text;
      bubbles[roomYou.id] = text;
      roomPeople.forEach(function (person) {
        if (person.id === roomYou.id) person.bubble = text;
      });
      paintPeople(roomPeople);
      var live = $("lounge-live");
      if (live) live.textContent = "Du: " + text;
      if (roomId) loungeApi("/api/lounge/line", { id: roomId, text: text }).catch(function () {});
    });
  }

  var floorKeys = $("lounge-floor");
  if (floorKeys) {
    floorKeys.addEventListener("keydown", function (event) {
      if (event.key === "ArrowRight" || event.key === "ArrowDown") {
        event.preventDefault();
        goSpot(spotIndex + 1);
      } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
        event.preventDefault();
        goSpot(spotIndex - 1);
      }
    });
  }
})();
