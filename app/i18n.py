"""Vertalingen voor servermeldingen (console) en game-teksten.

De taal wordt door de interface ingesteld via het websocket-bericht
``set_language``; default is Nederlands ("nl").
"""

DEFAULT_LANGUAGE = "nl"

MESSAGES: dict[str, dict[str, str]] = {
    # -- verbinding -----------------------------------------------------------
    "no_connection": {
        "nl": "Geen verbinding met de robotarm: kan {action} niet uitvoeren",
        "en": "No connection to the robot arm: cannot {action}",
    },
    "scanning": {
        "nl": "Scannen naar CYNUS-/CMR-apparaten...",
        "en": "Scanning for CYNUS/CMR devices...",
    },
    "scan_failed": {
        "nl": "Scan mislukt: {error}",
        "en": "Scan failed: {error}",
    },
    "scan_done": {
        "nl": "Scan klaar: {count} apparaat/apparaten gevonden",
        "en": "Scan finished: {count} device(s) found",
    },
    "connecting": {
        "nl": "Verbinden met {address}...",
        "en": "Connecting to {address}...",
    },
    "connected": {
        "nl": "Verbonden met {name} ({address})",
        "en": "Connected to {name} ({address})",
    },
    "connect_failed": {
        "nl": "Verbinden mislukt: {error}",
        "en": "Connecting failed: {error}",
    },
    "connect_no_address": {
        "nl": "Geen apparaatadres opgegeven",
        "en": "No device address provided",
    },
    "disconnect_failed": {
        "nl": "Verbreken mislukt: {error}",
        "en": "Disconnect failed: {error}",
    },
    "disconnected": {
        "nl": "Verbinding verbroken",
        "en": "Disconnected",
    },
    "arm_disconnected": {
        "nl": "Verbinding met de arm verbroken",
        "en": "Connection to the arm lost",
    },
    "send_failed": {
        "nl": "Versturen mislukt: {error}",
        "en": "Sending failed: {error}",
    },
    "handler_error": {
        "nl": "Interne fout bij opdracht: {error}",
        "en": "Internal error handling command: {error}",
    },
    "pending_scan_timeout": {
        "nl": "Timeout: geen FEN ontvangen na scan board (30s) – sync geannuleerd",
        "en": "Timeout: no FEN received after scan board (30s) – sync cancelled",
    },
    "pending_check_timeout": {
        "nl": "Timeout: geen FEN ontvangen voor controle (30s)",
        "en": "Timeout: no FEN received for check (30s)",
    },
    "robot_move_busy": {
        "nl": "Robotzet bezig; wacht tot Stockfish klaar is",
        "en": "Robot move in progress; wait until Stockfish finishes",
    },
    "engine_settings_invalid": {
        "nl": "Ongeldige engine-instelling: {error}",
        "en": "Invalid engine setting: {error}",
    },
    "pgn_too_large": {
        "nl": "PGN te groot (max. {max} tekens)",
        "en": "PGN too large (max. {max} characters)",
    },
    # -- acties (ingevuld in no_connection) -----------------------------------
    "action.send_move": {"nl": "zet versturen", "en": "send move"},
    "action.send_command": {"nl": "commando versturen", "en": "send command"},
    "action.set_side": {"nl": "kleur naar robot sturen", "en": "send color to robot"},
    "action.check": {"nl": "controle uitvoeren", "en": "perform check"},
    "action.scan_board": {"nl": "scan board uitvoeren", "en": "perform scan board"},
    "action.robot_move": {"nl": "robot laten zetten", "en": "let the robot move"},
    "action.replay_next": {"nl": "replayzet uitvoeren", "en": "execute replay move"},
    "action.force_move": {"nl": "override-zet versturen", "en": "send override move"},
    # -- spel / bord -----------------------------------------------------------
    "new_game": {
        "nl": "Nieuw spel – partij gereset",
        "en": "New game – game reset",
    },
    "check_ok": {
        "nl": "Controle OK: robotstelling komt overeen met de app/engine",
        "en": "Check OK: robot position matches the app/engine",
    },
    "check_bad": {
        "nl": "Controle FOUT: robotstelling wijkt af van de app/engine",
        "en": "Check MISMATCH: robot position differs from the app/engine",
    },
    "replay_scan_mismatch": {
        "nl": "Replay: scan van de arm wijkt af van de verwachte stelling; zet de stukken gelijk aan het bord in de app",
        "en": "Replay: arm scan differs from the expected position; make the pieces match the board in the app",
    },
    "scan_keep_gap": {
        "nl": "Scan board: stelling wijkt af van de verwachte stelling (historie behouden)",
        "en": "Scan board: position differs from the expected position (history kept)",
    },
    "scan_keep_ok": {
        "nl": "Scan board: stelling klopt, zettenlijst behouden",
        "en": "Scan board: position matches, move list kept",
    },
    "scan_synced": {
        "nl": "Scan board: stelling gesynchroniseerd, zettenlijst geleegd",
        "en": "Scan board: position synchronized, move list cleared",
    },
    "board_synced": {
        "nl": "Bord gesynchroniseerd (nieuw/start)",
        "en": "Board synchronized (new/start)",
    },
    "board_gap": {
        "nl": "Bord bijgewerkt zonder zetpad; zettenhistorie behouden",
        "en": "Board updated without a move path; move history kept",
    },
    "move_detected": {
        "nl": "Zet gedetecteerd: {move}",
        "en": "Move detected: {move}",
    },
    "auto_check_bad": {
        "nl": "Automatische controle FOUT: scan wijkt af van de verwachte stelling",
        "en": "Automatic check MISMATCH: scan differs from the expected position",
    },
    "scan_board_sent": {
        "nl": "scan board verstuurd – wacht op FEN",
        "en": "scan board sent – waiting for FEN",
    },
    "wait_current_scan": {
        "nl": "Wacht eerst tot de lopende bordscan klaar is",
        "en": "Wait until the current board scan is finished",
    },
    "check_started": {
        "nl": "Controle gestart – robot scant nu het bord",
        "en": "Check started – robot is scanning the board",
    },
    "checkmate": {"nl": "Schaakmat!", "en": "Checkmate!"},
    "check": {"nl": "Schaak!", "en": "Check!"},
    # -- engine ----------------------------------------------------------------
    "get_move": {
        "nl": "Arm vraagt om een zet (get move)",
        "en": "Arm requests a move (get move)",
    },
    "auto_mode_off_no_move": {
        "nl": "Automodus staat uit; geen zet verstuurd",
        "en": "Auto mode is off; no move sent",
    },
    "replay_active_block": {
        "nl": "PGN-replay actief; stop eerst het naspelen voordat Stockfish zet",
        "en": "PGN replay active; stop the replay before Stockfish moves",
    },
    "wait_scan": {
        "nl": "Wacht eerst op de nieuwe bordscan na kleurwissel/sync",
        "en": "Wait for the new board scan after color change/sync",
    },
    "no_fen_fallback": {
        "nl": "Geen FEN van de arm; gebruik huidige/startstelling",
        "en": "No FEN from the arm; using current/start position",
    },
    "engine_unavailable": {
        "nl": "Engine niet beschikbaar: {error}",
        "en": "Engine not available: {error}",
    },
    "ponder_cache": {
        "nl": "Stockfish gebruikt pondering-cache ({reason})",
        "en": "Stockfish uses pondering cache ({reason})",
    },
    "ponder_finish": {
        "nl": "Stockfish rondt pondering af ({reason})...",
        "en": "Stockfish is finishing pondering ({reason})...",
    },
    "engine_analyzing": {
        "nl": "Stockfish analyseert ({reason})...",
        "en": "Stockfish is analyzing ({reason})...",
    },
    "engine_chooses": {
        "nl": "Stockfish kiest {move} ({score})",
        "en": "Stockfish chooses {move} ({score})",
    },
    "engine_updated": {
        "nl": "Engine-instellingen bijgewerkt: {settings}",
        "en": "Engine settings updated: {settings}",
    },
    "reason.manual": {"nl": "handmatig", "en": "manual"},
    "reason.get_move": {"nl": "get move", "en": "get move"},
    "reason.robot_move_button": {
        "nl": "knop Laat robot zetten",
        "en": "Let robot move button",
    },
    # -- kleur / modus ----------------------------------------------------------
    "invalid_color": {
        "nl": "Ongeldige kleur; gebruik w of b",
        "en": "Invalid color; use w or b",
    },
    "side_set": {
        "nl": "Kleur ingesteld: jij={human}, robot={robot}, flip board {flip}",
        "en": "Color set: you={human}, robot={robot}, flip board {flip}",
    },
    "scan_after_side": {
        "nl": "scan board verstuurd na kleurwissel – wacht op FEN",
        "en": "scan board sent after color change – waiting for FEN",
    },
    "auto_enabled": {"nl": "Automodus aan", "en": "Auto mode on"},
    "auto_disabled": {"nl": "Automodus uit", "en": "Auto mode off"},
    "unknown_type": {
        "nl": "Onbekend berichttype: {type}",
        "en": "Unknown message type: {type}",
    },
    "language_set": {
        "nl": "Taal ingesteld op Nederlands",
        "en": "Language set to English",
    },
    # -- handmatige zetten -------------------------------------------------------
    "move_legal": {
        "nl": "Handmatige zet legaal: {san} ({uci})",
        "en": "Manual move legal: {san} ({uci})",
    },
    "move_rejected": {
        "nl": "Handmatige zet afgekeurd: {uci} ({reason})",
        "en": "Manual move rejected: {uci} ({reason})",
    },
    "move_override": {
        "nl": "Override: illegale zet toch verstuurd: {uci}",
        "en": "Override: illegal move sent anyway: {uci}",
    },
    # -- PGN replay ---------------------------------------------------------------
    "pgn_load_failed": {
        "nl": "PGN laden mislukt: {reason}",
        "en": "Loading PGN failed: {reason}",
    },
    "pgn_loaded": {
        "nl": "PGN geladen: {white} - {black}, {total} zetten. Zet de stukken in de beginstand.",
        "en": "PGN loaded: {white} - {black}, {total} moves. Set up the pieces in the starting position.",
    },
    "replay_info": {"nl": "Replay: {reason}", "en": "Replay: {reason}"},
    "replay_move": {
        "nl": "Replayzet {index}/{total}: {san} ({uci})",
        "en": "Replay move {index}/{total}: {san} ({uci})",
    },
    "replay_done": {
        "nl": "Partij volledig nagespeeld. Kies je kleur om verder te spelen tegen Stockfish.",
        "en": "Game fully replayed. Choose your color to continue playing against Stockfish.",
    },
    "replay_stopped": {
        "nl": "Naspelen gestopt. Kies je kleur om verder te spelen tegen Stockfish.",
        "en": "Replay stopped. Choose your color to continue playing against Stockfish.",
    },
    "replay_auto_started": {
        "nl": "Automatisch naspelen gestart (elke {seconds}s een zet)",
        "en": "Automatic replay started (one move every {seconds}s)",
    },
    "replay_auto_stopped": {
        "nl": "Automatisch naspelen gestopt",
        "en": "Automatic replay stopped",
    },
    "replay_auto_finished": {
        "nl": "Automatisch naspelen voltooid",
        "en": "Automatic replay finished",
    },
    "replay_auto_busy": {
        "nl": "Automatisch naspelen loopt al",
        "en": "Automatic replay is already running",
    },
    "replay_auto_not_active": {
        "nl": "Geen actieve PGN-replay om automatisch na te spelen",
        "en": "No active PGN replay to play automatically",
    },
    # -- game.py: validatie en PGN-redenen ------------------------------------------
    "invalid_fen": {
        "nl": "Ongeldige FEN: {fen}",
        "en": "Invalid FEN: {fen}",
    },
    "reason.empty_move": {"nl": "Lege zet", "en": "Empty move"},
    "reason.no_position": {
        "nl": "Nog geen bordstelling bekend; scan eerst het bord",
        "en": "No board position known yet; scan the board first",
    },
    "reason.bad_uci": {
        "nl": "Ongeldig UCI-formaat, gebruik bijvoorbeeld e2e4 of h7h8q",
        "en": "Invalid UCI format, use e.g. e2e4 or h7h8q",
    },
    "reason.illegal": {
        "nl": "Deze zet is niet legaal in de huidige stelling",
        "en": "This move is not legal in the current position",
    },
    "reason.pgn_empty": {"nl": "Leeg PGN-bestand", "en": "Empty PGN file"},
    "reason.pgn_unreadable": {
        "nl": "PGN kon niet gelezen worden: {error}",
        "en": "PGN could not be read: {error}",
    },
    "reason.pgn_no_game": {
        "nl": "Geen partij gevonden in het PGN-bestand",
        "en": "No game found in the PGN file",
    },
    "reason.pgn_errors": {
        "nl": "PGN bevat fouten: {error}",
        "en": "PGN contains errors: {error}",
    },
    "reason.pgn_fen_header": {
        "nl": "Alleen partijen vanuit de beginstand worden ondersteund (FEN-header gevonden)",
        "en": "Only games from the starting position are supported (FEN header found)",
    },
    "reason.pgn_no_moves": {
        "nl": "De partij bevat geen zetten",
        "en": "The game contains no moves",
    },
    "reason.no_pgn_loaded": {"nl": "Geen PGN geladen", "en": "No PGN loaded"},
    "reason.replay_finished": {
        "nl": "De partij is al volledig nagespeeld",
        "en": "The game has already been fully replayed",
    },
    # -- PGN-export ------------------------------------------------------------------
    "player_name": {"nl": "Speler", "en": "Player"},
}


def tr(lang: str, key: str, **params) -> str:
    """Vertaal een berichtsleutel; onbekende sleutels komen letterlijk terug."""
    entry = MESSAGES.get(key)
    if entry is None:
        return key
    text = entry.get(lang) or entry.get(DEFAULT_LANGUAGE) or key
    if params:
        try:
            return text.format(**params)
        except (KeyError, IndexError):
            return text
    return text
