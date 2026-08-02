# Installation

Guide for running the CYNUS Chess Arm web interface on a Windows PC that may not have Python installed yet. This project does not ship a packaged `.exe`; you run it from source with [uv](https://docs.astral.sh/uv/).

## Requirements

- Windows with Bluetooth (BLE) for the chess arm
- Internet access (to install uv, Python, and dependencies)
- A Stockfish executable (see below; optional to start the UI, required for auto mode)

## 1. Install uv

In PowerShell (no admin required):

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

Close and reopen PowerShell (or refresh `$env:Path`), then check:

```powershell
uv --version
```

## 2. Get the project

Clone or copy the repository, then open that folder:

```powershell
cd D:\Github\Cynus
```

## 3. Install Python via uv

uv can download Python for you (3.10+ is required):

```powershell
uv python install 3.12
```

## 4. Create the environment and install dependencies

There is no `pyproject.toml` yet; dependencies are listed in `requirements.txt`:

```powershell
uv venv
uv pip install -r requirements.txt
```

Alternatively, skip the separate activate step and use `uv run` (see [Starting](#7-start-the-app)).

## 5. Install Stockfish

Stockfish is a separate chess engine binary, not a Cynus executable.

1. Download Stockfish for Windows from https://stockfishchess.org/download/
2. Place the file in the project root or in `app\stockfish\` (any name starting with `stockfish` works, e.g. `stockfish-windows-x86-64-avx2.exe`), **or**
3. Set the full path:

```powershell
$env:STOCKFISH_PATH = "C:\path\to\stockfish.exe"
```

Without Stockfish the interface still starts, but auto mode will not work; this is reported in the UI.

## 6. Adjust engine defaults

Stockfish startup settings live in [`engine_defaults.json`](engine_defaults.json) at the project root. Edit this file for your machine and restart the app. Keys that start with `_` are comments and are ignored.

| Key | Meaning | Example |
| --- | ------- | ------- |
| `elo` | UCI_Elo strength (1320–3190) | `2000` |
| `analysis_depth` | Depth for candidate-move analysis | `15` |
| `movetime` | Think time for the played move (ms) | `5000` |
| `turn` | Robot side to move when building a FEN (`w` / `b`) | `"b"` |
| `candidates` | Number of MultiPV candidate lines (1–10) | `5` |
| `hash` | Hash table size in MB | `512` |
| `threads` | CPU threads for Stockfish | `4` |

The repository may ship with high `hash` / `threads` values tuned for a powerful machine. On a typical PC, lower them (for example `hash: 512` and `threads: 4`) so Stockfish does not request too much memory.

Values are clamped to safe ranges when loaded. If the file is missing or invalid, a conservative fallback is used (512 MB hash, 4 threads). The UI engine panel can still override settings for the current session; only this file sets the values used at startup.

## 7. Start the app

With `uv run` (recommended; uses `.venv` and the project Python):

```powershell
uv run --with-requirements requirements.txt python main.py
```

Or after `uv venv` + `uv pip install`:

```powershell
.venv\Scripts\python main.py
```

You can also use `starten.bat` / `starten.ps1` once `.venv` exists and dependencies are installed.

Then open http://127.0.0.1:8000 in the browser.

For development auto-reload:

```powershell
$env:CYNUS_RELOAD = "1"
uv run --with-requirements requirements.txt python main.py
```

Use **NL** / **EN** in the header to switch language.

## 8. Connect the chess arm

1. Turn on Bluetooth on the PC.
2. Turn on the chess arm.
3. In the UI, click **Scan**, then **Connect** (devices whose name starts with `CYNUS-` or `CMR`).

## Contact form (Formspree)

The UI footer Contact form uses the Formspree Vanilla JS SDK (`@formspree/ajax` from CDN) with form id `xpqvgnkq`. In the Formspree dashboard for that form: set your notification email, turn **Spam protection → reCAPTCHA** on, and leave **Custom reCAPTCHA Key** empty so Formspree’s built-in captcha is used. No email address or secrets belong in the project files. Internet access is required for the CDN script and form submit.

## Checklist

1. Install uv  
2. Open the project folder  
3. `uv python install 3.12`  
4. Install dependencies from `requirements.txt`  
5. Place a Stockfish executable  
6. Tune `engine_defaults.json` for your PC  
7. Start with `uv run … python main.py`  
8. Open the browser and connect the arm  
9. (Optional) Configure Formspree captcha for the Contact form (see above)  

## Alternative: classic venv + pip

If Python 3.10+ is already installed and you prefer not to use uv:

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```
