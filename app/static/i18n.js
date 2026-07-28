"use strict";

// ---------------------------------------------------------------------------
// Vertalingen voor de interface (NL default, EN optioneel).
// Statische teksten via data-i18n / data-i18n-placeholder / data-i18n-html;
// dynamische teksten via t(key, params) in app.js.
// ---------------------------------------------------------------------------

const TRANSLATIONS = {
  nl: {
    "app.title": "CYNUS Schaakarm",
    "title.server": "Serververbinding",
    "title.ble": "Bluetooth-verbinding",
    "aria.board": "Schaakbord",
    // header
    "server.connecting": "Server: verbinden...",
    "server.connected": "Server: verbonden",
    "server.reconnect": "Server: opnieuw verbinden...",
    "server.none": "Geen verbinding met de server",
    "arm.disconnected": "Arm: niet verbonden",
    // verbinding
    "panel.connection": "Verbinding",
    "btn.scan": "Scan",
    "btn.disconnect": "Verbreek verbinding",
    "btn.connect": "Verbind",
    "devices.placeholder": "Nog geen apparaten. Klik op \"Scan\".",
    "devices.none": "Geen CYNUS-/CMR-apparaten gevonden",
    // kleur
    "panel.side": "Jouw kleur",
    "side.hint_setup": "Stelt flip board in op de arm en de Stockfish-kleur voor de robot.",
    "btn.side_white": "Ik speel wit",
    "btn.side_black": "Ik speel zwart",
    "help.side_white": "Jij speelt wit; de robot (Stockfish) speelt zwart. Het bord op het scherm heeft wit onderaan.\nCommando's naar de arm:\n• set internal engine off\n• set flip board off\n• scan board\nAntwoord van de arm: fen: <stelling>",
    "help.side_black": "Jij speelt zwart; de robot (Stockfish) speelt wit. Het bord op het scherm heeft zwart onderaan.\nCommando's naar de arm:\n• set internal engine off\n• set flip board on\n• scan board\nAntwoord van de arm: fen: <stelling>\nGebruik daarna \"Laat robot zetten\" voor de openingszet van wit.",
    "side.status_default": "Huidig: jij wit, robot zwart (standaard)",
    "side.status": "Huidig: jij {human}, robot {robot} (flip board {flip})",
    "side.hint_white": "Jij speelt wit: doe je zet op het bord en druk daarna op de klok. De robot (zwart) antwoordt automatisch.",
    "side.hint_black": "Jij speelt zwart: druk níet op de klok aan het begin. Klik op \"Laat robot zetten\" zodat wit de openingszet doet. Daarna speel jij en druk je op de klok.",
    "btn.robot_move": "Laat robot zetten",
    "help.robot_move": "Laat Stockfish een zet berekenen voor de robotkleur en die door de arm uitvoeren. Handig als jij zwart speelt en wit de openingszet moet doen, of als de klok geen get move stuurt.\nCommando naar de arm: move <uci>\n(bijv. move e2e4)",
    "color.white": "wit",
    "color.black": "zwart",
    // engine
    "panel.engine": "Engine (Stockfish)",
    "engine.auto": "Automodus: antwoord automatisch op \"get move\"",
    "label.elo": "ELO",
    "label.analysis_depth": "Analyse-diepte",
    "label.movetime": "Denktijd (ms)",
    "label.hash": "Hash (MB)",
    "label.threads": "Threads",
    "label.turn": "Aan zet",
    "option.black": "Zwart (b)",
    "option.white": "Wit (w)",
    "label.candidates": "Kandidaten",
    "btn.apply": "Toepassen",
    "help.engine_apply": "Past de Stockfish-instellingen in dit paneel toe (ELO, analyse-diepte, denktijd, hash, threads, aan zet, kandidaten).\nGeen Bluetooth-commando naar de arm; alleen de lokale engine in de app wordt bijgewerkt.",
    "engine.thinking": "Stockfish denkt na…",
    "engine.unavailable": "Engine niet beschikbaar",
    "engine.last_move": "Laatste engine-zet: {move}",
    "th.move": "Zet",
    "th.score": "Score",
    "th.line": "Lijn",
    "candidates.none": "Geen kandidaten",
    "candidates.empty": "Nog geen analyse",
    // testpaneel
    "panel.test": "Testpaneel: commando's",
    "btn.send": "Verstuur",
    "test.preview": "Te versturen:",
    "test.param_none": "geen parameter nodig",
    "test.param_required": "\u2013 (parameter vereist)",
    "test.fill_param": "Vul eerst de parameter in",
    "test.arm_messages": "Berichten die de arm zelf stuurt",
    "proto.fen": "<code>fen: &lt;stelling&gt;</code> – bordstand (bij connect, klok of get fen/scan)",
    "proto.get_move": "<code>get move</code> – vraagt om een engine-zet (alleen als internal engine uit staat)",
    "proto.new_game": "<code>new game</code> – bij dubbelklik op de klokknop",
    "proto.status": "<code>robot is &lt;status&gt;</code> – antwoord op get robot status",
    "proto.other": "<code>serial ...</code> / batterij / versies – antwoorden op get-commando's",
    // bord
    "panel.board": "Bord",
    "moves.header": "Gespeelde zetten",
    "btn.download_pgn": "Download PGN",
    "moves.none": "Nog geen zetten",
    "label.board_size": "Bordgrootte",
    "size.small": "280px",
    "size.normal": "400px",
    "size.large": "520px",
    "size.xlarge": "640px",
    "size.800": "800px",
    "size.xxlarge": "1000px",
    "btn.scan_board": "Scan bord",
    "help.scan_board": "Synchroniseert de stelling van het fysieke bord met de app en wist de zettenlijst.\nCommando naar de arm: scan board\nAntwoord van de arm: fen: <stelling>",
    "btn.check": "Controle",
    "help.check": "Laat de robot het bord scannen en vergelijkt die stelling met de stelling in de app.\nCommando naar de arm: scan board\nAntwoord van de arm: fen: <stelling>\nResultaat: Controle OK of Controle FOUT (zonder de zettenlijst te wissen).",
    "check.not_done": "Controle: nog niet uitgevoerd",
    "check.busy": "Controle: bezig met FEN ophalen...",
    "check.ok": "Controle: OK, stelling klopt",
    "check.bad": "Controle: FOUT, robot={robot} app={app}",
    "board.no_position": "Nog geen stelling ontvangen",
    // handmatige zet
    "panel.move": "Handmatige zet",
    "move.placeholder": "bijv. e2e4",
    "btn.move_send": "Voer zet uit",
    "btn.force": "Toch uitvoeren",
    "move.accepted": "Zet geaccepteerd: {san} ({move})",
    "move.illegal": "Illegale zet {move}: {reason}",
    "move.forced": "Override uitgevoerd: {move} is toch verstuurd",
    // PGN naspelen
    "panel.replay": "PGN naspelen",
    "replay.hint_top": "Laad een partij vanuit de beginstand en laat de robot de zetten uitvoeren. Zet de stukken eerst in de beginstand.",
    "btn.pgn_load": "Laad PGN",
    "pgn.placeholder": "...of plak hier PGN-tekst en klik op Laad PGN",
    "btn.replay_next": "Volgende zet",
    "btn.replay_stop": "Stop naspelen",
    "label.replay_interval": "Interval (s)",
    "btn.replay_auto": "Automatisch naspelen",
    "btn.replay_auto_stop": "Stop automatisch",
    "replay.auto_running": "Automatisch bezig…",
    "replay.hint_continue": "Kies bij \"Jouw kleur\" wit of zwart om vanaf deze stelling verder te spelen tegen Stockfish.",
    "replay.progress": "Zet {x} van {n}",
    "replay.load_failed": "PGN laden mislukt",
    "pgn.choose": "Kies een .pgn-bestand of plak PGN-tekst",
    "pgn.read_error": "Bestand kon niet gelezen worden",
    // console
    "panel.console": "Console (rx/tx)",
    "btn.console_clear": "Wis console",
    // testcommando-labels
    "cmd.set-internal-engine": "set internal engine – built-in Stockfish aan/uit",
    "cmd.set-internal-engine.ph": "on of off",
    "cmd.set-flip-board": "set flip board – bord logisch omdraaien",
    "cmd.set-flip-board.ph": "on of off",
    "cmd.set-time": "set time – tijdmodus / unlimited",
    "cmd.set-time.ph": "bijv. 10 of unlimited",
    "cmd.get-fen": "get fen – vraag huidige stelling op",
    "cmd.move": "move – voer een zet fysiek uit",
    "cmd.move.ph": "bijv. e2e4 of h2h1q",
    "cmd.set-robot-turn": "set robot turn – scan + zet (als klokknop)",
    "cmd.scan-board": "scan board – scan bord, stuur FEN (geen zet)",
    "cmd.set-wait-minutes": "set wait minutes – slaaptijd (test)",
    "cmd.set-wait-minutes.ph": "bijv. 30",
    "cmd.get-wait-minutes": "get wait minutes – vraag slaaptijd op",
    "cmd.get-robot-status": "get robot status – vraag status op",
    "cmd.play-audio": "play audio – speel geluid af",
    "cmd.play-audio.ph": "check, checkmate of error",
    "cmd.play-txt": "play txt – toon tekst op scherm (max 10)",
    "cmd.play-txt.ph": "bijv. e2d2",
    "cmd.sync-time": "sync time – sync klokken zwart/wit",
    "cmd.sync-time.ph": "bijv. 5:03 7:22",
    "cmd.new-game": "new game – nieuw spel (meestal van arm)",
    "cmd.force-reset": "force reset – arm klaar voor scan",
    "cmd.force-fold": "force fold – arm inklappen voor opslag",
    "cmd.force-grab": "force grab – magneet omlaag (grijpen)",
    "cmd.force-release": "force release – magneet omhoog (loslaten)",
    "cmd.get-serial-number": "get serial number – serienummer",
    "cmd.get-battery": "get battery – accuspanning",
    "cmd.get-software-version": "get software version – softwareversie",
    "cmd.get-hardware-version": "get hardware version – hardwareversie",
    "cmd.move-force": "move force – zet zonder checks (test)",
    "cmd.move-force.ph": "bijv. e2e4 P of e2e4 P p",
    "cmd.raw": "Vrij commando – eigen tekst",
    "cmd.raw.ph": "typ een commando",
  },
  en: {
    "app.title": "CYNUS Chess Arm",
    "title.server": "Server connection",
    "title.ble": "Bluetooth connection",
    "aria.board": "Chessboard",
    "server.connecting": "Server: connecting...",
    "server.connected": "Server: connected",
    "server.reconnect": "Server: reconnecting...",
    "server.none": "No connection to the server",
    "arm.disconnected": "Arm: not connected",
    "panel.connection": "Connection",
    "btn.scan": "Scan",
    "btn.disconnect": "Disconnect",
    "btn.connect": "Connect",
    "devices.placeholder": "No devices yet. Click \"Scan\".",
    "devices.none": "No CYNUS/CMR devices found",
    "panel.side": "Your color",
    "side.hint_setup": "Sets flip board on the arm and the Stockfish color for the robot.",
    "btn.side_white": "I play white",
    "btn.side_black": "I play black",
    "help.side_white": "You play white; the robot (Stockfish) plays black. The on-screen board shows white at the bottom.\nCommands to the arm:\n• set internal engine off\n• set flip board off\n• scan board\nReply from the arm: fen: <position>",
    "help.side_black": "You play black; the robot (Stockfish) plays white. The on-screen board shows black at the bottom.\nCommands to the arm:\n• set internal engine off\n• set flip board on\n• scan board\nReply from the arm: fen: <position>\nThen use \"Let robot move\" for white's opening move.",
    "side.status_default": "Current: you white, robot black (default)",
    "side.status": "Current: you {human}, robot {robot} (flip board {flip})",
    "side.hint_white": "You play white: make your move on the board and then press the clock. The robot (black) responds automatically.",
    "side.hint_black": "You play black: do not press the clock at the start. Click \"Let robot move\" so white makes the opening move. Then you play and press the clock.",
    "btn.robot_move": "Let robot move",
    "help.robot_move": "Have Stockfish calculate a move for the robot's color and let the arm execute it. Useful when you play black and white must open, or when the clock does not send get move.\nCommand to the arm: move <uci>\n(e.g. move e2e4)",
    "color.white": "white",
    "color.black": "black",
    "panel.engine": "Engine (Stockfish)",
    "engine.auto": "Auto mode: respond automatically to \"get move\"",
    "label.elo": "ELO",
    "label.analysis_depth": "Analysis depth",
    "label.movetime": "Think time (ms)",
    "label.hash": "Hash (MB)",
    "label.threads": "Threads",
    "label.turn": "To move",
    "option.black": "Black (b)",
    "option.white": "White (w)",
    "label.candidates": "Candidates",
    "btn.apply": "Apply",
    "help.engine_apply": "Applies the Stockfish settings in this panel (ELO, analysis depth, think time, hash, threads, side to move, candidates).\nNo Bluetooth command to the arm; only the local engine in the app is updated.",
    "engine.thinking": "Stockfish is thinking…",
    "engine.unavailable": "Engine not available",
    "engine.last_move": "Last engine move: {move}",
    "th.move": "Move",
    "th.score": "Score",
    "th.line": "Line",
    "candidates.none": "No candidates",
    "candidates.empty": "No analysis yet",
    "panel.test": "Test panel: commands",
    "btn.send": "Send",
    "test.preview": "To send:",
    "test.param_none": "no parameter needed",
    "test.param_required": "\u2013 (parameter required)",
    "test.fill_param": "Fill in the parameter first",
    "test.arm_messages": "Messages sent by the arm",
    "proto.fen": "<code>fen: &lt;position&gt;</code> – board state (on connect, clock or get fen/scan)",
    "proto.get_move": "<code>get move</code> – requests an engine move (only when internal engine is off)",
    "proto.new_game": "<code>new game</code> – on double-clicking the clock button",
    "proto.status": "<code>robot is &lt;status&gt;</code> – response to get robot status",
    "proto.other": "<code>serial ...</code> / battery / versions – responses to get commands",
    "panel.board": "Board",
    "moves.header": "Played moves",
    "btn.download_pgn": "Download PGN",
    "moves.none": "No moves yet",
    "label.board_size": "Board size",
    "size.small": "280px",
    "size.normal": "400px",
    "size.large": "520px",
    "size.xlarge": "640px",
    "size.800": "800px",
    "size.xxlarge": "1000px",
    "btn.scan_board": "Scan board",
    "help.scan_board": "Synchronizes the physical board position with the app and clears the move list.\nCommand to the arm: scan board\nReply from the arm: fen: <position>",
    "btn.check": "Check",
    "help.check": "Asks the robot to scan the board and compares that position with the app position.\nCommand to the arm: scan board\nReply from the arm: fen: <position>\nResult: Check OK or Check MISMATCH (without clearing the move list).",
    "check.not_done": "Check: not performed yet",
    "check.busy": "Check: fetching FEN...",
    "check.ok": "Check: OK, position matches",
    "check.bad": "Check: MISMATCH, robot={robot} app={app}",
    "board.no_position": "No position received yet",
    "panel.move": "Manual move",
    "move.placeholder": "e.g. e2e4",
    "btn.move_send": "Play move",
    "btn.force": "Execute anyway",
    "move.accepted": "Move accepted: {san} ({move})",
    "move.illegal": "Illegal move {move}: {reason}",
    "move.forced": "Override executed: {move} was sent anyway",
    "panel.replay": "PGN replay",
    "replay.hint_top": "Load a game from the starting position and let the robot execute the moves. Set up the pieces in the starting position first.",
    "btn.pgn_load": "Load PGN",
    "pgn.placeholder": "...or paste PGN text here and click Load PGN",
    "btn.replay_next": "Next move",
    "btn.replay_stop": "Stop replay",
    "label.replay_interval": "Interval (s)",
    "btn.replay_auto": "Auto replay",
    "btn.replay_auto_stop": "Stop auto",
    "replay.auto_running": "Auto replay running…",
    "replay.hint_continue": "Choose white or black under \"Your color\" to continue playing against Stockfish from this position.",
    "replay.progress": "Move {x} of {n}",
    "replay.load_failed": "Loading PGN failed",
    "pgn.choose": "Choose a .pgn file or paste PGN text",
    "pgn.read_error": "File could not be read",
    "panel.console": "Console (rx/tx)",
    "btn.console_clear": "Clear console",
    "cmd.set-internal-engine": "set internal engine – built-in Stockfish on/off",
    "cmd.set-internal-engine.ph": "on or off",
    "cmd.set-flip-board": "set flip board – flip the board logically",
    "cmd.set-flip-board.ph": "on or off",
    "cmd.set-time": "set time – time mode / unlimited",
    "cmd.set-time.ph": "e.g. 10 or unlimited",
    "cmd.get-fen": "get fen – request current position",
    "cmd.move": "move – physically execute a move",
    "cmd.move.ph": "e.g. e2e4 or h2h1q",
    "cmd.set-robot-turn": "set robot turn – scan + move (like clock button)",
    "cmd.scan-board": "scan board – scan board, send FEN (no move)",
    "cmd.set-wait-minutes": "set wait minutes – sleep time (test)",
    "cmd.set-wait-minutes.ph": "e.g. 30",
    "cmd.get-wait-minutes": "get wait minutes – request sleep time",
    "cmd.get-robot-status": "get robot status – request status",
    "cmd.play-audio": "play audio – play a sound",
    "cmd.play-audio.ph": "check, checkmate or error",
    "cmd.play-txt": "play txt – show text on screen (max 10)",
    "cmd.play-txt.ph": "e.g. e2d2",
    "cmd.sync-time": "sync time – sync clocks black/white",
    "cmd.sync-time.ph": "e.g. 5:03 7:22",
    "cmd.new-game": "new game – new game (usually from arm)",
    "cmd.force-reset": "force reset – arm ready for scan",
    "cmd.force-fold": "force fold – fold arm for storage",
    "cmd.force-grab": "force grab – magnet down (grab)",
    "cmd.force-release": "force release – magnet up (release)",
    "cmd.get-serial-number": "get serial number – serial number",
    "cmd.get-battery": "get battery – battery voltage",
    "cmd.get-software-version": "get software version – software version",
    "cmd.get-hardware-version": "get hardware version – hardware version",
    "cmd.move-force": "move force – move without checks (test)",
    "cmd.move-force.ph": "e.g. e2e4 P or e2e4 P p",
    "cmd.raw": "Free command – custom text",
    "cmd.raw.ph": "type a command",
  },
};

let currentLang = localStorage.getItem("cynus-lang") || "nl";
if (!TRANSLATIONS[currentLang]) currentLang = "nl";

function t(key, params) {
  const dict = TRANSLATIONS[currentLang] || TRANSLATIONS.nl;
  let text = dict[key];
  if (text === undefined) text = TRANSLATIONS.nl[key];
  if (text === undefined) return key;
  if (params) {
    for (const [name, value] of Object.entries(params)) {
      text = text.split(`{${name}}`).join(String(value));
    }
  }
  return text;
}

function applyLanguage() {
  document.documentElement.lang = currentLang;
  document.title = t("app.title");
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-html]").forEach((el) => {
    el.innerHTML = t(el.dataset.i18nHtml);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    el.title = t(el.dataset.i18nTitle);
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
    el.setAttribute("aria-label", t(el.dataset.i18nAria));
  });
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.lang === currentLang);
  });
}

function getLanguage() {
  return currentLang;
}

function setLanguage(lang) {
  if (!TRANSLATIONS[lang]) return;
  currentLang = lang;
  localStorage.setItem("cynus-lang", lang);
  applyLanguage();
  if (typeof onLanguageChanged === "function") {
    onLanguageChanged();
  }
}
