"use strict";

// ---------------------------------------------------------------------------
// Protocolcommando's (Cynus BLE protocol v3.7 / documentation/Protocol.txt).
// {param} in het template wordt vervangen door de inhoud van het parameterveld.
// Labels en placeholders komen uit i18n.js (sleutels cmd.<id> en cmd.<id>.ph).
// ---------------------------------------------------------------------------
const COMMANDS = [
  { id: "display-txt", template: "display txt {param}", param: { required: true } },
  { id: "force-fold", template: "force fold", param: null },
  { id: "force-grab", template: "force grab", param: null },
  { id: "force-release", template: "force release", param: null },
  { id: "force-reset", template: "force reset", param: null },
  { id: "get-battery", template: "get battery", param: null },
  { id: "get-fen", template: "get fen", param: null },
  { id: "get-hardware-version", template: "get hardware version", param: null },
  { id: "get-robot-status", template: "get robot status", param: null },
  { id: "get-serial-number", template: "get serial number", param: null },
  { id: "get-software-version", template: "get software version", param: null },
  { id: "get-wait-minutes", template: "get wait minutes", param: null },
  { id: "move", template: "move {param}", param: { required: true } },
  { id: "move-force", template: "move {param}", param: { required: true } },
  { id: "new-game", template: "new game", param: null },
  { id: "play-audio", template: "play audio {param}", param: { required: true } },
  { id: "scan-board", template: "scan board", param: null },
  { id: "set-flip-board", template: "set flip board {param}", param: { required: true } },
  { id: "set-internal-engine", template: "set internal engine {param}", param: { required: true } },
  { id: "set-robot-turn", template: "set robot turn", param: null },
  { id: "set-time", template: "set time {param}", param: { required: true } },
  { id: "set-timer-mode", template: "set timer mode {param}", param: { required: true } },
  { id: "set-volume", template: "set volume {param}", param: { required: true } },
  { id: "set-wait-minutes", template: "set wait minutes {param}", param: { required: true } },
  { id: "sync-time", template: "sync time {param}", param: { required: true } },
  { id: "toon-text", template: "toon_text {param}", param: { required: true } },
  // Altijd onderaan
  { id: "raw", template: "{param}", param: { required: true } },
];

const $ = (id) => document.getElementById(id);

const ROBOT_REQUIRED_BUTTONS = [
  "btn-side-white", "btn-side-black",
  "btn-cmd-send", "btn-scan-board", "btn-check-position",
  "btn-new-game", "btn-move-send",
];

let ws = null;
let pendingIllegalMove = null;

// Laatst ontvangen berichten, zodat de UI bij een taalwissel opnieuw
// gerenderd kan worden in de nieuwe taal.
const lastState = {
  status: null,
  board: null,
  side: null,
  replay: null,
  replayAuto: { running: false, interval: 10 },
  check: null,
  engineMove: null,
  engineMoveSource: null,
  candidates: null,
  candidatesHighlightBest: true,
};

// -- WebSocket ---------------------------------------------------------------

function connectWs() {
  ws = new WebSocket(`ws://${location.host}/ws`);

  ws.onopen = () => {
    $("server-dot").classList.add("on");
    $("server-status").textContent = t("server.connected");
    send({ type: "set_language", language: getLanguage() });
  };

  ws.onclose = () => {
    $("server-dot").classList.remove("on");
    $("server-status").textContent = t("server.reconnect");
    setTimeout(connectWs, 2000);
  };

  ws.onmessage = (event) => {
    let msg;
    try {
      msg = JSON.parse(event.data);
    } catch (_) {
      return;
    }
    switch (msg.type) {
      case "status": onStatus(msg); break;
      case "devices": onDevices(msg.devices); break;
      case "board": onBoard(msg); break;
      case "engine": onEngine(msg); break;
      case "engine_move": onEngineMove(msg); break;
      case "engine_thinking": onEngineThinking(true); break;
      case "check_result": onCheckResult(msg); break;
      case "scan_recovery": onScanRecovery(msg); break;
      case "move_validation": onMoveValidation(msg); break;
      case "move_forced": onMoveForced(msg); break;
      case "replay": onReplay(msg); break;
      case "replay_error": onReplayError(msg); break;
      case "replay_auto": onReplayAuto(msg); break;
      case "auto": $("auto-mode").checked = msg.enabled; break;
      case "pgn_databases": onPgnDatabases(msg); break;
      case "side": onSide(msg); break;
      case "log": addLog(msg.dir, msg.text); break;
    }
  };

  ws.onerror = () => {
    /* onclose handelt reconnect af */
  };
}

function send(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(msg));
  } else {
    addLog("info", t("server.none"));
  }
}

// -- Verbinding & apparaten ----------------------------------------------------

function setAppVersion(version) {
  if (!version) return;
  const el = $("app-version");
  if (el) el.textContent = `v${version}`;
}

function isRobotOpeningMoveNeeded() {
  /** Alleen nodig als robot wit is én er nog geen zetten gespeeld zijn. */
  const connected = !!(lastState.status && lastState.status.connected);
  if (!connected) return false;
  const side = lastState.side;
  if (!side || side.robot !== "w") return false;
  const board = lastState.board;
  if (!board) return true; // kleur gekozen, nog geen bord: openingszet toestaan
  const moves = board.moves || [];
  if (moves.length > 0) return false;
  const rows = board.move_rows || [];
  if (rows.some((r) => r.w || r.b)) return false;
  // Beginstand: wit aan zet (of turn nog onbekend).
  if (board.turn && board.turn !== "w") return false;
  return true;
}

function updateRobotMoveButton() {
  const btn = $("btn-robot-move");
  if (btn) btn.disabled = !isRobotOpeningMoveNeeded();
}

function onStatus(msg) {
  lastState.status = msg;
  setAppVersion(msg.version);
  const dot = $("ble-dot");
  const label = $("ble-status");
  if (msg.connected) {
    dot.classList.add("on");
    label.textContent = `Arm: ${msg.name || msg.address}`;
    $("btn-disconnect").disabled = false;
  } else {
    dot.classList.remove("on");
    label.textContent = t("arm.disconnected");
    $("btn-disconnect").disabled = true;
  }
  for (const id of ROBOT_REQUIRED_BUTTONS) {
    const btn = $(id);
    if (btn) btn.disabled = !msg.connected;
  }
  updateRobotMoveButton();
}

async function loadVersion() {
  try {
    const res = await fetch("/api/version");
    if (!res.ok) return;
    const data = await res.json();
    setAppVersion(data.version);
  } catch (_) {
    /* negeer; WebSocket-status kan alsnog vullen */
  }
}

function onDevices(devices) {
  const list = $("device-list");
  list.innerHTML = "";
  if (!devices.length) {
    const li = document.createElement("li");
    li.className = "placeholder";
    li.textContent = t("devices.none");
    list.appendChild(li);
    return;
  }
  for (const d of devices) {
    const li = document.createElement("li");
    const info = document.createElement("span");
    info.innerHTML = `${escapeHtml(d.name)}<br><span class="addr">${escapeHtml(d.address)}</span>`;
    const btn = document.createElement("button");
    btn.textContent = t("btn.connect");
    btn.addEventListener("click", () => send({ type: "connect", address: d.address }));
    li.appendChild(info);
    li.appendChild(btn);
    list.appendChild(li);
  }
}

// -- Bord (SVG + SAN van de server) ------------------------------------------

function applyBoardSize(sizePx) {
  const boardEl = $("board");
  boardEl.style.setProperty("--board-size", `${sizePx}px`);
  boardEl.dataset.size = String(sizePx);
  const list = $("move-list");
  if (list) list.style.maxHeight = `${sizePx}px`;
}

function onBoard(msg) {
  lastState.board = msg;
  const boardEl = $("board");
  if (msg.svg) {
    boardEl.innerHTML = msg.svg;
    applyBoardSize($("board-size").value);
  }
  const turnEl = $("board-turn");
  if (turnEl) {
    turnEl.classList.remove("white", "black");
    if (msg.turn === "w") {
      turnEl.textContent = t("board.turn_white");
      turnEl.classList.add("white");
    } else if (msg.turn === "b") {
      turnEl.textContent = t("board.turn_black");
      turnEl.classList.add("black");
    } else {
      turnEl.textContent = t("board.turn_unknown");
    }
  }
  $("board-fen").textContent = msg.fen || t("board.no_position");
  renderMoveList(msg.move_rows || null, msg.moves || []);
  updateRobotMoveButton();
  if (msg.error) {
    addLog("info", msg.error);
  }
}

function renderMoveList(rows, moves) {
  const list = $("move-list");
  list.innerHTML = "";

  // Prefer structured rows from the server; fall back to flat SAN list.
  if (!rows) {
    rows = [];
    for (let i = 0; i < moves.length; i += 2) {
      rows.push({
        n: Math.floor(i / 2) + 1,
        w: moves[i] || null,
        b: moves[i + 1] || null,
      });
    }
  }

  if (!rows.length) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = t("moves.none");
    list.appendChild(li);
    return;
  }

  for (const row of rows) {
    const li = document.createElement("li");
    const ply = document.createElement("span");
    ply.className = "ply";
    ply.textContent = `${row.n}.`;
    const white = document.createElement("span");
    white.className = "san";
    white.textContent = row.w || (row.b && !row.w ? "\u2026" : "");
    const black = document.createElement("span");
    black.className = "san";
    black.textContent = row.b || "";
    li.appendChild(ply);
    li.appendChild(white);
    li.appendChild(black);
    list.appendChild(li);
  }
  list.scrollTop = list.scrollHeight;
}

// -- Engine ---------------------------------------------------------------------

function onEngine(msg) {
  const warn = $("engine-warning");
  if (!msg.available) {
    warn.textContent = msg.error || t("engine.unavailable");
    warn.classList.remove("hidden");
  } else {
    warn.classList.add("hidden");
  }
  const s = msg.settings || {};
  if (s.elo !== undefined) $("eng-elo").value = s.elo;
  if (s.analysis_depth !== undefined) $("eng-analysis-depth").value = s.analysis_depth;
  if (s.movetime !== undefined) $("eng-movetime").value = s.movetime;
  if (s.hash !== undefined) $("eng-hash").value = s.hash;
  if (s.threads !== undefined) $("eng-threads").value = s.threads;
  if (s.turn !== undefined) $("eng-turn").value = s.turn;
  if (s.candidates !== undefined) $("eng-candidates").value = s.candidates;
}

function onEngineThinking(active) {
  $("engine-thinking").classList.toggle("hidden", !active);
}

function parseCandidateCount(score) {
  if (score == null) return 0;
  const m = String(score).match(/^(\d+)\s*x$/i);
  return m ? parseInt(m[1], 10) : 0;
}

function updateMoveSourceBadge(source, visible) {
  const badge = $("move-source-badge");
  if (!badge) return;
  badge.classList.remove("database", "stockfish", "hint");
  if (!visible || !source) {
    badge.classList.add("hidden");
    badge.textContent = "";
    return;
  }
  if (source === "database_hint") {
    badge.textContent = t("source.database_hint");
    badge.classList.add("hint");
    badge.classList.remove("hidden");
  } else if (source === "database") {
    badge.textContent = t("source.database");
    badge.classList.add("database");
    badge.classList.remove("hidden");
  } else if (source === "stockfish") {
    badge.textContent = t("source.stockfish");
    badge.classList.add("stockfish");
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
    badge.textContent = "";
  }
}

function updateScoreColumnHeader(source) {
  const th = $("th-score");
  if (!th) return;
  if (source === "database") {
    th.textContent = t("th.count");
    th.setAttribute("data-i18n", "th.count");
  } else {
    th.textContent = t("th.score");
    th.setAttribute("data-i18n", "th.score");
  }
}

function onEngineMove(msg) {
  const move = typeof msg === "string" ? msg : msg.move;
  const source = typeof msg === "object" && msg ? msg.source : null;
  const suggestion = !!(msg && msg.suggestion);
  const candidates = msg && msg.candidates ? msg.candidates : null;
  const uiSource = suggestion && source === "database" ? "database_hint" : source;

  onEngineThinking(false);
  if (suggestion) {
    // Suggesties voor de speler: kandidatentabel vullen, geen gekozen robotzet.
    lastState.engineMoveSource = uiSource;
    lastState.candidatesHighlightBest = false;
    $("engine-last-move").textContent = candidates && candidates.length
      ? t("engine.pgn_suggestions")
      : t("engine.pgn_suggestions_none");
    updateMoveSourceBadge(uiSource, true);
    updateScoreColumnHeader("database");
    if (candidates) renderCandidates(candidates);
    return;
  }

  lastState.engineMove = move || null;
  lastState.engineMoveSource = source || null;
  lastState.candidatesHighlightBest = true;
  if (move) {
    const key = source === "database" ? "engine.last_move_db" : "engine.last_move";
    $("engine-last-move").textContent = t(key, { move });
  } else {
    $("engine-last-move").textContent = "";
  }
  updateMoveSourceBadge(source, !!move);
  updateScoreColumnHeader(source === "database" ? "database" : "stockfish");
  if (candidates) {
    renderCandidates(candidates);
  }
}

function renderCandidates(candidates) {
  lastState.candidates = candidates;
  const tbody = $("engine-candidates").querySelector("tbody");
  tbody.innerHTML = "";
  if (!candidates || !candidates.length) {
    const tr = document.createElement("tr");
    tr.className = "empty";
    const td = document.createElement("td");
    td.colSpan = 4;
    td.textContent = t("candidates.none");
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }
  const fromDb = lastState.engineMoveSource === "database"
    || lastState.engineMoveSource === "database_hint";
  const highlightBest = lastState.candidatesHighlightBest !== false;
  candidates.forEach((c, index) => {
    const tr = document.createElement("tr");
    if (highlightBest && index === 0) tr.className = "best";

    const rank = document.createElement("td");
    rank.textContent = String(c.multipv || index + 1);

    const move = document.createElement("td");
    const strong = document.createElement("strong");
    strong.textContent = c.san || c.move;
    move.appendChild(strong);

    const score = document.createElement("td");
    score.className = "score";
    if (fromDb) {
      const count = parseCandidateCount(c.score);
      score.textContent = count ? t("pgn.choice_count", { count }) : (c.score || "–");
    } else {
      score.textContent = c.score || "–";
      if (c.mate != null) {
        score.classList.add(Number(c.mate) > 0 ? "good" : "bad");
      } else if (c.centipawn != null) {
        score.classList.add(Number(c.centipawn) >= 0 ? "good" : "bad");
      }
    }

    const pv = document.createElement("td");
    pv.className = "pv";
    pv.textContent = c.pv || "";

    tr.appendChild(rank);
    tr.appendChild(move);
    tr.appendChild(score);
    tr.appendChild(pv);
    tbody.appendChild(tr);
  });
}

function onSide(msg) {
  lastState.side = msg;
  const human = msg.human === "b" ? t("color.black") : t("color.white");
  const robot = msg.robot === "b" ? t("color.black") : t("color.white");
  $("side-status").textContent = t("side.status", { human, robot, flip: msg.flip });
  $("btn-side-white").classList.toggle("active", msg.human === "w");
  $("btn-side-black").classList.toggle("active", msg.human === "b");
  if (msg.robot) {
    $("eng-turn").value = msg.robot;
  }
  const hint = $("side-hint");
  hint.textContent = msg.human === "b" ? t("side.hint_black") : t("side.hint_white");
  const flipWarn = $("side-flip-warning");
  if (flipWarn) {
    if (msg.human === "b") {
      flipWarn.textContent = t("side.flip_warning");
      flipWarn.classList.remove("hidden");
    } else {
      flipWarn.classList.add("hidden");
    }
  }
  updateRobotMoveButton();
}

function onCheckResult(msg) {
  lastState.check = msg;
  const el = $("check-status");
  el.classList.remove("ok", "bad");
  if (msg.ok) {
    el.classList.add("ok");
    el.textContent = t("check.ok");
  } else {
    el.classList.add("bad");
    el.textContent = t("check.bad", { robot: msg.robot_fen, app: msg.expected_fen });
  }
}

function onScanRecovery(msg) {
  lastState.scanRecovery = msg;
  const modal = $("scan-recovery-modal");
  if (!modal) return;
  if (msg.active) {
    $("scan-recovery-robot").textContent = msg.robot_fen || "";
    $("scan-recovery-app").textContent = msg.expected_fen || "";
    modal.classList.remove("hidden");
  } else {
    modal.classList.add("hidden");
  }
}

// -- Contact (Formspree @formspree/ajax) ------------------------------------

function openContactModal() {
  const modal = $("contact-modal");
  if (!modal) return;
  modal.classList.remove("hidden");
  const name = $("contact-name");
  if (name) name.focus();
}

function closeContactModal() {
  const modal = $("contact-modal");
  if (!modal) return;
  modal.classList.add("hidden");
}

function initContactForm() {
  const openBtn = $("btn-contact");
  const cancelBtn = $("btn-contact-cancel");
  const form = $("contact-form");
  const modal = $("contact-modal");
  if (!openBtn || !form || !modal) return;
  openBtn.addEventListener("click", openContactModal);
  if (cancelBtn) cancelBtn.addEventListener("click", closeContactModal);
  // Submit wordt afgehandeld door @formspree/ajax (geen preventDefault hier).
  form.addEventListener(
    "submit",
    (event) => {
      const gotcha = form.querySelector('input[name="_gotcha"]');
      if (gotcha && gotcha.value.trim()) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    },
    true
  );
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeContactModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.classList.contains("hidden")) {
      closeContactModal();
    }
  });
}

function onMoveValidation(msg) {
  const el = $("move-validation");
  const forceBtn = $("btn-force-move");
  el.classList.remove("hidden", "ok");
  if (msg.ok) {
    pendingIllegalMove = null;
    el.classList.add("ok");
    el.textContent = t("move.accepted", { san: msg.san, move: msg.move });
    forceBtn.classList.add("hidden");
    $("move-input").value = "";
    return;
  }

  pendingIllegalMove = msg.move;
  el.textContent = t("move.illegal", { move: msg.move, reason: msg.reason });
  forceBtn.classList.remove("hidden");
}

function onMoveForced(msg) {
  const el = $("move-validation");
  const forceBtn = $("btn-force-move");
  pendingIllegalMove = null;
  el.classList.remove("hidden");
  el.classList.add("ok");
  el.textContent = t("move.forced", { move: msg.move });
  forceBtn.classList.add("hidden");
  $("move-input").value = "";
}

function clearMoveValidation() {
  pendingIllegalMove = null;
  $("move-validation").classList.add("hidden");
  $("move-validation").classList.remove("ok");
  $("move-validation").textContent = "";
  $("btn-force-move").classList.add("hidden");
}

// -- PGN naspelen -----------------------------------------------------------

function onReplay(msg) {
  lastState.replay = msg;
  $("replay-error").classList.add("hidden");

  const info = $("replay-info");
  const movesEl = $("replay-moves");
  const progress = $("replay-progress");
  const hint = $("replay-hint");
  const btnNext = $("btn-replay-next");
  const btnStop = $("btn-replay-stop");
  const btnAuto = $("btn-replay-auto");
  const btnAutoStop = $("btn-replay-auto-stop");

  if (!msg.loaded) {
    info.classList.add("hidden");
    movesEl.classList.add("hidden");
    progress.classList.add("hidden");
    hint.classList.add("hidden");
    btnNext.disabled = true;
    btnStop.disabled = true;
    btnAuto.disabled = true;
    btnAutoStop.disabled = true;
    return;
  }

  // Verse lading: oude engine-/controle-informatie opruimen.
  if (msg.active && msg.index === 0) {
    renderCandidates([]);
    lastState.engineMove = null;
    lastState.engineMoveSource = null;
    lastState.check = null;
    $("engine-last-move").textContent = "";
    updateMoveSourceBadge(null, false);
    updateScoreColumnHeader("stockfish");
    onEngineThinking(false);
    const check = $("check-status");
    check.classList.remove("ok", "bad");
    check.textContent = t("check.not_done");
    clearMoveValidation();
  }

  const h = msg.headers || {};
  info.classList.remove("hidden");
  info.textContent = `${h.white || "?"} – ${h.black || "?"}` +
    (h.result && h.result !== "*" ? ` (${h.result})` : "") +
    (h.event ? `, ${h.event}` : "");

  movesEl.classList.remove("hidden");
  movesEl.innerHTML = "";
  (msg.sans || []).forEach((san, i) => {
    if (i % 2 === 0) {
      const num = document.createElement("span");
      num.className = "num";
      num.textContent = `${Math.floor(i / 2) + 1}.`;
      movesEl.appendChild(num);
    }
    const span = document.createElement("span");
    span.className = "san" + (i < msg.index ? " played" : "");
    if (i === msg.index - 1) span.classList.add("current");
    span.textContent = san;
    movesEl.appendChild(span);
  });
  const current = movesEl.querySelector(".san.current");
  if (current) current.scrollIntoView({ block: "nearest" });

  progress.classList.remove("hidden");
  progress.textContent = t("replay.progress", { x: msg.index, n: msg.total });

  const done = msg.index >= msg.total;
  const autoRunning = !!(lastState.replayAuto && lastState.replayAuto.running);
  btnNext.disabled = !msg.active || done || autoRunning;
  btnStop.disabled = !msg.active && !autoRunning;
  btnAuto.disabled = !msg.active || done || autoRunning;
  btnAutoStop.disabled = !autoRunning;
  hint.classList.toggle("hidden", (msg.active || autoRunning) && !done);
}

function onReplayAuto(msg) {
  lastState.replayAuto = {
    running: !!msg.running,
    interval: msg.interval != null ? msg.interval : 10,
  };
  if (msg.interval != null) {
    $("replay-interval").value = String(msg.interval);
  }
  if (lastState.replay) onReplay(lastState.replay);
}

function onReplayError(msg) {
  const el = $("replay-error");
  el.classList.remove("hidden");
  el.textContent = msg.reason || t("replay.load_failed");
}

function loadPgnFile() {
  const input = $("pgn-file");
  const file = input.files && input.files[0];
  if (file) {
    const reader = new FileReader();
    reader.onload = () => {
      send({ type: "load_pgn", pgn: String(reader.result || "") });
    };
    reader.onerror = () => addLog("info", t("pgn.read_error"));
    reader.readAsText(file);
    return;
  }

  const text = $("pgn-text").value.trim();
  if (!text) {
    addLog("info", t("pgn.choose"));
    return;
  }
  send({ type: "load_pgn", pgn: text });
}

function updateCandidatesPanelVisibility(pgnEnabled) {
  const panel = $("panel-candidates");
  if (panel) panel.classList.toggle("hidden", !pgnEnabled);
}

function onPgnDatabases(msg) {
  const toggle = $("pgn-mode");
  if (toggle) toggle.checked = !!msg.enabled;
  const variations = $("pgn-variations");
  if (variations) variations.checked = !!msg.include_variations;
  updateCandidatesPanelVisibility(!!msg.enabled);

  const select = $("pgn-database-select");
  if (!select) return;

  const databases = Array.isArray(msg.databases) ? msg.databases : [];
  const active = msg.active || "";
  const prev = select.value;

  select.innerHTML = "";
  const none = document.createElement("option");
  none.value = "";
  none.textContent = t("option.pgn_none");
  none.setAttribute("data-i18n", "option.pgn_none");
  select.appendChild(none);

  for (const name of databases) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    select.appendChild(opt);
  }

  if (active && databases.includes(active)) {
    select.value = active;
  } else if (prev && databases.includes(prev)) {
    select.value = prev;
  } else {
    select.value = "";
  }
}

function uploadPgnDatabase() {
  const input = $("pgn-database-file");
  const file = input.files && input.files[0];
  if (!file) {
    addLog("info", t("pgn.db_choose"));
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    send({
      type: "upload_pgn_database",
      name: file.name,
      pgn: String(reader.result || ""),
    });
    input.value = "";
  };
  reader.onerror = () => addLog("info", t("pgn.read_error"));
  reader.readAsText(file);
}

function deletePgnDatabase() {
  const select = $("pgn-database-select");
  const name = select && select.value;
  if (!name) {
    addLog("info", t("pgn.db_delete_none"));
    return;
  }
  if (!confirm(t("pgn.db_delete_confirm", { name }))) return;
  send({ type: "delete_pgn_database", name });
}

// -- Console ---------------------------------------------------------------------

const MAX_CONSOLE_LINES = 500;

function addLog(dir, text) {
  const line = document.createElement("div");
  line.className = `line ${dir}`;
  const time = document.createElement("span");
  time.className = "time";
  time.textContent = new Date().toLocaleTimeString();
  const prefix = dir === "rx" ? "\u2190 " : dir === "tx" ? "\u2192 " : "";
  line.appendChild(time);
  line.appendChild(document.createTextNode(prefix + text));
  const consoleEl = $("console");
  consoleEl.appendChild(line);
  while (consoleEl.children.length > MAX_CONSOLE_LINES) {
    consoleEl.removeChild(consoleEl.firstChild);
  }
  consoleEl.scrollTop = consoleEl.scrollHeight;
}

// -- Testpaneel -------------------------------------------------------------------

function selectedCommand() {
  return COMMANDS.find((c) => c.id === $("cmd-select").value) || COMMANDS[0];
}

function buildCommandString() {
  const cmd = selectedCommand();
  const param = $("cmd-param").value.trim();
  if (cmd.param && cmd.param.required && !param) return null;
  if (cmd.id === "toon-text") {
    const parsed = parseToonTextParam(param);
    if (!parsed) return null;
    if (parsed.duration <= 0) {
      return `toon_text ${parsed.text} (${t("test.toon_stays")})`;
    }
    return `toon_text ${parsed.text} (${parsed.duration}s)`;
  }
  return cmd.template.replace("{param}", param);
}

/** Parse "tekst", "tekst,5" of "tekst,0" → { text, duration }; default 10; 0 = blijvend. */
function parseToonTextParam(param) {
  const raw = (param || "").trim();
  if (!raw) return null;
  const m = raw.match(/^(.*),(\d+(?:\.\d+)?)\s*$/);
  if (m) {
    const text = m[1].trim();
    if (!text) return null;
    return { text, duration: Number(m[2]) };
  }
  return { text: raw, duration: 10 };
}

function updateCmdUi() {
  const cmd = selectedCommand();
  const paramInput = $("cmd-param");
  if (cmd.param) {
    paramInput.disabled = false;
    paramInput.placeholder = t(`cmd.${cmd.id}.ph`);
  } else {
    paramInput.disabled = true;
    paramInput.value = "";
    paramInput.placeholder = t("test.param_none");
  }
  const preview = buildCommandString();
  $("cmd-preview").textContent = preview || t("test.param_required");
}

function renderCommandOptions() {
  const select = $("cmd-select");
  const selected = select.value;
  select.innerHTML = "";
  for (const cmd of COMMANDS) {
    const opt = document.createElement("option");
    opt.value = cmd.id;
    opt.textContent = t(`cmd.${cmd.id}`);
    select.appendChild(opt);
  }
  if (selected) select.value = selected;
}

function initTestPanel() {
  renderCommandOptions();
  const select = $("cmd-select");
  select.addEventListener("change", updateCmdUi);
  $("cmd-param").addEventListener("input", updateCmdUi);
  $("btn-cmd-send").addEventListener("click", () => {
    const cmd = selectedCommand();
    const param = $("cmd-param").value.trim();
    if (cmd.param && cmd.param.required && !param) {
      addLog("info", t("test.fill_param"));
      return;
    }
    if (cmd.id === "toon-text") {
      const parsed = parseToonTextParam(param);
      if (!parsed) {
        addLog("info", t("test.fill_param"));
        return;
      }
      send({ type: "toon_text", text: parsed.text, duration: parsed.duration });
      return;
    }
    const command = buildCommandString();
    if (!command) {
      addLog("info", t("test.fill_param"));
      return;
    }
    send({ type: "send_raw", command });
  });
  updateCmdUi();
}

// -- Taalwissel -----------------------------------------------------------------

// Wordt aangeroepen door setLanguage() in i18n.js na applyLanguage().
function onLanguageChanged() {
  renderCommandOptions();
  updateCmdUi();

  // Dynamische onderdelen opnieuw renderen in de nieuwe taal.
  if (ws && ws.readyState === WebSocket.OPEN) {
    $("server-status").textContent = t("server.connected");
  }
  if (lastState.status) onStatus(lastState.status);
  if (lastState.board) onBoard(lastState.board); else renderMoveList(null, []);
  if (lastState.side) onSide(lastState.side);
  if (lastState.replay) onReplay(lastState.replay);
  if (lastState.check) onCheckResult(lastState.check);
  if (lastState.engineMoveSource === "database_hint") {
    $("engine-last-move").textContent = lastState.candidates && lastState.candidates.length
      ? t("engine.pgn_suggestions")
      : t("engine.pgn_suggestions_none");
    updateMoveSourceBadge("database_hint", true);
    updateScoreColumnHeader("database");
  } else if (lastState.engineMove) {
    const key = lastState.engineMoveSource === "database"
      ? "engine.last_move_db"
      : "engine.last_move";
    $("engine-last-move").textContent = t(key, { move: lastState.engineMove });
    updateMoveSourceBadge(lastState.engineMoveSource, true);
    updateScoreColumnHeader(
      lastState.engineMoveSource === "database" ? "database" : "stockfish"
    );
  }
  if (lastState.candidates) {
    renderCandidates(lastState.candidates);
  }

  send({ type: "set_language", language: getLanguage() });
}

// -- Overige knoppen -----------------------------------------------------------------

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = String(text);
  return div.innerHTML;
}

function init() {
  applyLanguage();
  loadVersion();
  initTestPanel();
  renderMoveList(null, []);
  applyBoardSize($("board-size").value);

  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => setLanguage(btn.dataset.lang));
  });

  $("board-size").addEventListener("change", (e) => {
    applyBoardSize(e.target.value);
  });
  $("btn-scan-board").addEventListener("click", () => {
    send({ type: "scan_board" });
  });
  $("btn-check-position").addEventListener("click", () => {
    const el = $("check-status");
    el.classList.remove("ok", "bad");
    el.textContent = t("check.busy");
    send({ type: "check_position" });
  });
  $("btn-scan-recovery-stop").addEventListener("click", () => {
    send({ type: "cancel_scan_recovery" });
  });
  initContactForm();
  $("btn-new-game").addEventListener("click", () => {
    if (!window.confirm(t("new_game.confirm"))) return;
    const check = $("check-status");
    check.classList.remove("ok", "bad");
    check.textContent = t("check.not_done");
    clearMoveValidation();
    send({ type: "new_game" });
  });
  $("btn-download-pgn").addEventListener("click", () => {
    window.location.href = "/download/pgn";
  });

  $("btn-side-white").addEventListener("click", () => {
    onSide({ human: "w", robot: "b", flip: "off" });
    send({ type: "set_side", color: "w" });
  });
  $("btn-side-black").addEventListener("click", () => {
    onSide({ human: "b", robot: "w", flip: "on" });
    send({ type: "set_side", color: "b" });
  });
  $("btn-robot-move").addEventListener("click", () => {
    send({ type: "robot_move" });
  });

  $("btn-scan").addEventListener("click", () => send({ type: "scan" }));
  $("btn-disconnect").addEventListener("click", () => send({ type: "disconnect" }));

  $("btn-move-send").addEventListener("click", () => {
    const move = $("move-input").value.trim();
    if (move) {
      send({ type: "send_move", move });
    }
  });
  $("btn-force-move").addEventListener("click", () => {
    if (pendingIllegalMove) {
      send({ type: "force_send_move", move: pendingIllegalMove });
    }
  });
  $("btn-pgn-load").addEventListener("click", loadPgnFile);
  // Bestand en geplakte tekst sluiten elkaar uit: de laatst gekozen bron telt.
  $("pgn-file").addEventListener("change", () => {
    if ($("pgn-file").files.length) $("pgn-text").value = "";
  });
  $("pgn-text").addEventListener("input", () => {
    if ($("pgn-text").value.trim()) $("pgn-file").value = "";
  });
  $("btn-replay-next").addEventListener("click", () => send({ type: "replay_next" }));
  $("btn-replay-stop").addEventListener("click", () => send({ type: "replay_stop" }));
  $("btn-replay-auto").addEventListener("click", () => {
    const interval = Number($("replay-interval").value) || 10;
    send({ type: "replay_auto_start", interval });
  });
  $("btn-replay-auto-stop").addEventListener("click", () => {
    send({ type: "replay_auto_stop" });
  });
  $("move-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") $("btn-move-send").click();
  });
  $("move-input").addEventListener("input", () => {
    clearMoveValidation();
  });

  $("auto-mode").addEventListener("change", (e) => {
    send({ type: "toggle_auto", enabled: e.target.checked });
  });

  $("pgn-mode").addEventListener("change", (e) => {
    updateCandidatesPanelVisibility(e.target.checked);
    send({ type: "toggle_pgn_mode", enabled: e.target.checked });
  });
  const pgnMode = $("pgn-mode");
  updateCandidatesPanelVisibility(!!(pgnMode && pgnMode.checked));
  $("pgn-variations").addEventListener("change", (e) => {
    send({ type: "toggle_pgn_variations", enabled: e.target.checked });
  });
  $("pgn-database-select").addEventListener("change", (e) => {
    send({ type: "set_pgn_database", name: e.target.value || "" });
  });
  $("btn-pgn-database-upload").addEventListener("click", uploadPgnDatabase);
  $("btn-pgn-database-search").addEventListener("click", () => {
    updateCandidatesPanelVisibility(true);
    send({ type: "search_pgn_database" });
  });
  $("btn-pgn-database-delete").addEventListener("click", deletePgnDatabase);

  function clampInt(value, min, max) {
    const n = parseInt(value, 10);
    if (Number.isNaN(n)) return null;
    return Math.max(min, Math.min(max, n));
  }

  function applyEngineSettings() {
    const elo = clampInt($("eng-elo").value, 1000, 4000);
    const threads = clampInt($("eng-threads").value, 2, 40);
    if (elo === null || threads === null) return;
    $("eng-elo").value = String(elo);
    $("eng-threads").value = String(threads);
    send({
      type: "set_engine",
      settings: {
        elo,
        analysis_depth: $("eng-analysis-depth").value,
        movetime: $("eng-movetime").value,
        hash: $("eng-hash").value,
        threads,
        turn: $("eng-turn").value,
        candidates: $("eng-candidates").value,
      },
    });
  }

  for (const id of [
    "eng-elo",
    "eng-analysis-depth",
    "eng-movetime",
    "eng-hash",
    "eng-threads",
    "eng-turn",
    "eng-candidates",
  ]) {
    $(id).addEventListener("change", applyEngineSettings);
  }

  $("btn-calculate-move").addEventListener("click", () => {
    send({ type: "calculate_move" });
  });

  $("btn-console-clear").addEventListener("click", () => {
    $("console").innerHTML = "";
  });

  connectWs();
}

init();
