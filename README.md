# CYNUS Chess Arm web interface

Version: see [`VERSION`](VERSION) (currently the single source of truth for the app version).

Local web interface for the CYNUS robotic chess arm. A Python backend talks to
the arm over Bluetooth Low Energy (bleak) and lets Stockfish calculate moves
automatically; the browser shows the board live and provides manual controls
plus a test panel for protocol commands. The UI is bilingual (Dutch / English,
default Dutch).

## Requirements

- Windows with Bluetooth (BLE), Python 3.10+
- A Stockfish executable (see below)

## Installation

See [`Installation.md`](Installation.md) for the full setup guide, including a
fresh Windows PC with no Python installed (using [uv](https://docs.astral.sh/uv/)),
Stockfish, and `engine_defaults.json`.

Quick start if Python 3.10+ and for example a ide (cusor or pycharm for example) is already available:

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

Or use `starten.bat` / `starten.ps1`. Then open http://127.0.0.1:8000 in the browser.

For development auto-reload: `$env:CYNUS_RELOAD=1; .venv\Scripts\python main.py`

Use **NL** / **EN** in the header to switch language.

## Usage

1. Turn on the chess arm and click **Scan**. Devices whose name starts with
   `CYNUS-` or `CMR` appear in the list.
2. Click **Connect**. The status indicator at the top turns green when connected.
3. Choose **I play white** or **I play black** (sets flip board on the arm and
   Stockfish’s color for the robot).
4. Play a move on the physical board. The arm sends the new position
   (`fen: ...`) and requests a move (`get move`); with auto mode on, Stockfish
   calculates the best move and the arm executes it.
5. In the engine panel you can set ELO, analysis depth, think time, hash,
   threads, side to move, and number of candidate moves.
6. With **Manual move** you can send a UCI move (e.g. `e2e4`) to the arm.
   Illegal moves are blocked with a warning; you can still force them.
7. **PGN replay** loads a game from the starting position (file or pasted text)
   and lets the robot play the moves one by one; afterwards you can choose a
   color and continue against Stockfish.
8. The **Test panel** has a dropdown with all known protocol commands
   (`move <uci>`, free command, etc.). Everything sent and received appears in
   the console (rx/tx). Use **toon_text** there to show temporary text on the
   arm screen (max 10 characters; clears after 10 seconds).
9. While connected, the app shows who is to move on the arm screen (`Wit` /
   `Zwart` or `White` / `Black`) via `toon_text` → protocol `display txt`.
   The text clears automatically after 10 seconds.

## Automatic PGN backup (`pgn/`)

Played games are written automatically under [`pgn/`](pgn/) at the project root:

| File | Meaning |
| --- | --- |
| `pgn/current.pgn` | Latest state of the ongoing game (updated after each move) |
| `pgn/YYYY-MM-DD_HHMMSS.pgn` | Archive created when a game with moves is cleared (New game, side change, load another PGN, or return to the starting position) |

If the on-screen move list disappears, open the matching file from `pgn/` (or paste its contents) under **PGN replay** to restore the game. These files are local and gitignored (`pgn/*.pgn`).

## Protocol

Derived from `documentation/ble_stockfish2.py` and `documentation/Protocol.txt`:

| Direction  | Message             | Meaning                                    |
| ---------- | ------------------- | ------------------------------------------ |
| arm → host | `fen: <position>`   | Piece placement after each move            |
| arm → host | `get move`          | The arm requests an engine move            |
| host → arm | `move e2e4\r\n`     | The arm physically executes the move       |
| host → arm | `play audio check`  | Play “check” / “checkmate” / “error” audio |
| host → arm | `display txt …`     | Text on the arm screen (max 10 characters) |
| host → arm | `<text>\r\n`        | Free command                               |

Communication uses BLE characteristic `FFF1` (notify + write). New commands for
the test panel are added to the `COMMANDS` array at the top of
`app/static/app.js`.

## Project structure

- `VERSION` – app version number (edit this file to bump the version)
- `Installation.md` – full install guide (uv, Stockfish, engine defaults)
- `engine_defaults.json` – Stockfish start settings for this machine (hash, threads, …)
- `pgn/` – automatic PGN backups (`current.pgn` + timestamped archives)
- `app/server.py` – FastAPI server with WebSocket between browser and backend
- `app/version.py` – reads `VERSION`
- `app/ble_manager.py` – BLE scan, connection, and protocol handling
- `app/engine.py` – Stockfish wrapper
- `app/game.py` – game state with python-chess (SVG board + SAN moves)
- `app/pgn_store.py` – writes PGN backups to `pgn/`
- `app/i18n.py` – server-side message translations (NL/EN)
- `app/static/` – web interface (HTML/CSS/JS, no build step; `i18n.js` for UI strings)
- `documentation/` – protocol and examples

## Disclaimer

This software is provided as is, without warranty. Made with [Cursor](https://cursor.com).
