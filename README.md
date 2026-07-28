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

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### Stockfish

Download Stockfish from https://stockfishchess.org/download/ and do one of the following:

- Place the exe in the project folder (any name starting with `stockfish` works,
  e.g. `stockfish_20011801_x64.exe`), or in `app/stockfish/`, or
- Set the `STOCKFISH_PATH` environment variable to the full path of the exe.

Without Stockfish the interface still starts, but auto mode will not work; this
is reported in the UI.

### Engine defaults (`engine_defaults.json`)

Stockfish startup settings live in [`engine_defaults.json`](engine_defaults.json)
at the project root. Edit this file for your machine and restart the app.
Keys that start with `_` are comments and are ignored.

| Key | Meaning | Example |
| --- | ------- | ------- |
| `elo` | UCI_Elo strength (1320–3190) | `2000` |
| `analysis_depth` | Depth for candidate-move analysis | `15` |
| `movetime` | Think time for the played move (ms) | `5000` |
| `turn` | Robot side to move when building a FEN (`w` / `b`) | `"b"` |
| `candidates` | Number of MultiPV candidate lines (1–10) | `5` |
| `hash` | Hash table size in MB | `30720` |
| `threads` | CPU threads for Stockfish | `20` |

Values are clamped to safe ranges when loaded. If the file is missing or
invalid, a conservative fallback is used (512 MB hash, 4 threads). The UI
engine panel can still override settings for the current session; only this
file sets the values used at startup.

## Starting

```powershell
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
   the console (rx/tx).

## Protocol

Derived from `documentation/ble_stockfish2.py` and `documentation/Protocol.txt`:

| Direction  | Message             | Meaning                                    |
| ---------- | ------------------- | ------------------------------------------ |
| arm → host | `fen: <position>`   | Piece placement after each move            |
| arm → host | `get move`          | The arm requests an engine move            |
| host → arm | `move e2e4\r\n`     | The arm physically executes the move       |
| host → arm | `play audio check`  | Play “check” / “checkmate” / “error” audio |
| host → arm | `<text>\r\n`        | Free command                               |

Communication uses BLE characteristic `FFF1` (notify + write). New commands for
the test panel are added to the `COMMANDS` array at the top of
`app/static/app.js`.

## Project structure

- `VERSION` – app version number (edit this file to bump the version)
- `engine_defaults.json` – Stockfish start settings for this machine (hash, threads, …)
- `app/server.py` – FastAPI server with WebSocket between browser and backend
- `app/version.py` – reads `VERSION`
- `app/ble_manager.py` – BLE scan, connection, and protocol handling
- `app/engine.py` – Stockfish wrapper
- `app/game.py` – game state with python-chess (SVG board + SAN moves)
- `app/i18n.py` – server-side message translations (NL/EN)
- `app/static/` – web interface (HTML/CSS/JS, no build step; `i18n.js` for UI strings)
- `documentation/` – protocol and examples
